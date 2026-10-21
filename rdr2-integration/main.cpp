#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <xinput.h>

#include "main.h"
#include "natives.h"

#include <string>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
#include <sstream>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "xinput.lib")

// --- Thread-Safe Communication State ---
std::mutex g_netMutex;
std::vector<std::string> g_outgoingQueue;
std::string g_currentSubtitle = "";
std::string g_currentSpeaker = "Stranger";
std::string g_currentTranscription = "";
DWORD g_subtitleExpireTime = 0;

std::atomic<bool> g_bNetRunning(true);
std::atomic<bool> g_bConnected(false);
std::atomic<bool> g_bTurnOffSpinner(false);

DWORD g_busySpinnerExpireTime = 0;

// Background TCP client to send and receive from Python bridge (127.0.0.1:8765)
void NetworkWorker()
{
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0)
        return;

    while (g_bNetRunning)
    {
        SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (sock == INVALID_SOCKET)
        {
            std::this_thread::sleep_for(std::chrono::seconds(2));
            continue;
        }

        sockaddr_in serverAddr{};
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(8765);
        inet_pton(AF_INET, "127.0.0.1", &serverAddr.sin_addr);

        if (connect(sock, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR)
        {
            closesocket(sock);
            g_bConnected = false;
            std::this_thread::sleep_for(std::chrono::seconds(2));
            continue;
        }

        g_bConnected = true;

        DWORD timeout = 50; // ms
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout, sizeof(timeout));

        std::string recvBuffer;
        char tempBuf[1024];

        while (g_bNetRunning)
        {
            // 1. Send outgoing messages
            std::vector<std::string> toSend;
            {
                std::lock_guard<std::mutex> lock(g_netMutex);
                if (!g_outgoingQueue.empty())
                {
                    toSend.swap(g_outgoingQueue);
                }
            }

            for (const auto& msg : toSend)
            {
                std::string packet = msg + "\n";
                send(sock, packet.c_str(), (int)packet.length(), 0);
            }

            // 2. Receive incoming messages
            int bytesRecv = recv(sock, tempBuf, sizeof(tempBuf) - 1, 0);
            if (bytesRecv > 0)
            {
                tempBuf[bytesRecv] = '\0';
                recvBuffer += tempBuf;

                size_t newlinePos;
                while ((newlinePos = recvBuffer.find('\n')) != std::string::npos)
                {
                    std::string line = recvBuffer.substr(0, newlinePos);
                    recvBuffer.erase(0, newlinePos + 1);

                    // Parse transcription key if present
                    std::string transcription = "";
                    size_t transKey = line.find("\"transcription\"");
                    if (transKey != std::string::npos)
                    {
                        size_t colon = line.find(':', transKey + 15);
                        if (colon != std::string::npos)
                        {
                            size_t q1 = line.find('\"', colon + 1);
                            if (q1 != std::string::npos)
                            {
                                size_t q2 = line.find('\"', q1 + 1);
                                if (q2 != std::string::npos)
                                {
                                    transcription = line.substr(q1 + 1, q2 - (q1 + 1));
                                }
                            }
                        }
                    }

                    // Parse speaker name if present
                    std::string speaker = "Stranger";
                    size_t speakerKey = line.find("\"speaker\"");
                    if (speakerKey != std::string::npos)
                    {
                        size_t colon = line.find(':', speakerKey + 9);
                        if (colon != std::string::npos)
                        {
                            size_t q1 = line.find('\"', colon + 1);
                            if (q1 != std::string::npos)
                            {
                                size_t q2 = line.find('\"', q1 + 1);
                                if (q2 != std::string::npos)
                                {
                                    speaker = line.substr(q1 + 1, q2 - (q1 + 1));
                                }
                            }
                        }
                    }

                    // Parse text key
                    size_t keyPos = line.find("\"text\"");
                    if (keyPos != std::string::npos)
                    {
                        size_t colonPos = line.find(':', keyPos + 6);
                        if (colonPos != std::string::npos)
                        {
                            size_t quoteStart = line.find('\"', colonPos + 1);
                            if (quoteStart != std::string::npos)
                            {
                                size_t quoteEnd = line.find('\"', quoteStart + 1);
                                if (quoteEnd != std::string::npos)
                                {
                                    std::string sub = line.substr(quoteStart + 1, quoteEnd - (quoteStart + 1));
                                    std::lock_guard<std::mutex> lock(g_netMutex);
                                    g_currentSpeaker = speaker;
                                    g_currentSubtitle = sub;
                                    g_currentTranscription = transcription;
                                    g_subtitleExpireTime = GetTickCount() + 8000; // 8 seconds
                                    g_bTurnOffSpinner = true; // Stop the thinking spinner
                                }
                            }
                        }
                    }
                }
            }
            else if (bytesRecv == 0)
            {
                break;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }

        closesocket(sock);
        g_bConnected = false;
    }

    WSACleanup();
}

void EnqueueMessage(const std::string& msg)
{
    std::lock_guard<std::mutex> lock(g_netMutex);
    g_outgoingQueue.push_back(msg);
}

// 1. Top-Left Native Help Text (where all RDR2 prompts/tutorials appear)
void DrawTopLeftHelp(const std::string& text)
{
    HUD::SET_TEXT_SCALE(0.34f, 0.34f);
    HUD::_SET_TEXT_COLOR(255, 255, 255, 240);
    HUD::SET_TEXT_CENTRE(false); // Left aligned
    HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, 220);

    const char* str = MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", text.c_str());
    HUD::_DISPLAY_TEXT(str, 0.04f, 0.05f); // Top-left corner
}

// 2. Authentic RDR2 Dialogue Subtitles (Player STT + Yellow Speaker + White Dialogue)
void DrawDialogueSubtitle(const std::string& speaker, const std::string& text, const std::string& transcription)
{
    // If transcription exists, render Arthur's dialogue line above NPC subtitle
    if (!transcription.empty() && transcription != "(Silence)" && transcription != "(Inaudible audio)")
    {
        HUD::SET_TEXT_SCALE(0.32f, 0.32f);
        HUD::_SET_TEXT_COLOR(180, 220, 255, 230); // Soft Ice-Blue for Arthur
        HUD::SET_TEXT_CENTRE(true);
        HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, 240);
        std::string arthurFormatted = "Arthur: \"" + transcription + "\"";
        const char* arthurStr = MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", arthurFormatted.c_str());
        HUD::_DISPLAY_TEXT(arthurStr, 0.5f, 0.88f); // Directly above NPC dialogue
    }

    HUD::SET_TEXT_SCALE(0.36f, 0.36f);
    HUD::_SET_TEXT_COLOR(255, 255, 255, 255);
    HUD::SET_TEXT_CENTRE(true);
    HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, 240);

    // Format: ~COLOR_YELLOW~Speaker:~s~ "Dialogue"
    std::string formatted;
    if (!speaker.empty())
    {
        formatted = "~COLOR_YELLOW~" + speaker + ":~s~ \"" + text + "\"";
    }
    else
    {
        formatted = "\"" + text + "\"";
    }

    const char* str = MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", formatted.c_str());
    HUD::_DISPLAY_TEXT(str, 0.5f, 0.92f); // Exact RDR2 subtitle position (bottom center)
}

// Check if an action is pressed on padIndex 0 (player control), enabled or disabled
inline bool IsActionDown(Hash control)
{
    return (PAD::IS_CONTROL_PRESSED(0, control) != 0) ||
           (PAD::IS_DISABLED_CONTROL_PRESSED(0, control) != 0);
}

// Disable control action for the player so vanilla game actions don't trigger
inline void DisableAction(Hash control)
{
    PAD::DISABLE_CONTROL_ACTION(0, control, true);
}

// Check physical controller A button across all 4 XInput controller slots
bool IsControllerAPressed()
{
    XINPUT_STATE state;
    ZeroMemory(&state, sizeof(XINPUT_STATE));
    for (DWORD i = 0; i < 4; ++i)
    {
        if (XInputGetState(i, &state) == ERROR_SUCCESS)
        {
            if (state.Gamepad.wButtons & XINPUT_GAMEPAD_A)
            {
                return true;
            }
        }
    }
    return false;
}

// Native RDR2 UI prompt for Voice NPC Speak
Prompt g_voicePrompt = 0;
Ped g_lastPromptPed = 0;

void DeleteVoicePrompt()
{
    if (g_voicePrompt != 0 && HUD::_UIPROMPT_IS_VALID(g_voicePrompt))
    {
        HUD::_UIPROMPT_DELETE(g_voicePrompt);
        g_voicePrompt = 0;
    }
}

void UpdateVoicePrompt(Ped targetPed)
{
    if (targetPed != g_lastPromptPed)
    {
        DeleteVoicePrompt();
        g_lastPromptPed = targetPed;

        if (targetPed != 0 && ENTITY::DOES_ENTITY_EXIST(targetPed) && !ENTITY::IS_ENTITY_DEAD(targetPed) && PED::IS_PED_HUMAN(targetPed))
        {
            int groupId = HUD::_UIPROMPT_GET_GROUP_ID_FOR_TARGET_ENTITY((Entity)targetPed);
            if (groupId != 0)
            {
                g_voicePrompt = HUD::_UIPROMPT_REGISTER_BEGIN();
                HUD::_UIPROMPT_SET_CONTROL_ACTION(g_voicePrompt, 0xD10A3A36); // INPUT_INTERACT_LOCKON_A
                const char* str = MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", "Speak");
                HUD::_UIPROMPT_SET_TEXT(g_voicePrompt, str);
                HUD::_UIPROMPT_SET_HOLD_INDEFINITELY_MODE(g_voicePrompt);
                HUD::_UIPROMPT_SET_PRIORITY(g_voicePrompt, 2);
                HUD::_UIPROMPT_SET_GROUP(g_voicePrompt, groupId, 0);
                HUD::_UIPROMPT_REGISTER_END(g_voicePrompt);

                HUD::_UIPROMPT_SET_VISIBLE(g_voicePrompt, true);
                HUD::_UIPROMPT_SET_ENABLED(g_voicePrompt, true);
            }
        }
    }
    else if (targetPed != 0 && g_voicePrompt == 0)
    {
        // If groupId wasn't ready on the first tick, attach as soon as it becomes valid
        if (ENTITY::DOES_ENTITY_EXIST(targetPed) && !ENTITY::IS_ENTITY_DEAD(targetPed) && PED::IS_PED_HUMAN(targetPed))
        {
            int groupId = HUD::_UIPROMPT_GET_GROUP_ID_FOR_TARGET_ENTITY((Entity)targetPed);
            if (groupId != 0)
            {
                g_voicePrompt = HUD::_UIPROMPT_REGISTER_BEGIN();
                HUD::_UIPROMPT_SET_CONTROL_ACTION(g_voicePrompt, 0xD10A3A36); // INPUT_INTERACT_LOCKON_A
                const char* str = MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", "Speak");
                HUD::_UIPROMPT_SET_TEXT(g_voicePrompt, str);
                HUD::_UIPROMPT_SET_HOLD_INDEFINITELY_MODE(g_voicePrompt);
                HUD::_UIPROMPT_SET_PRIORITY(g_voicePrompt, 2);
                HUD::_UIPROMPT_SET_GROUP(g_voicePrompt, groupId, 0);
                HUD::_UIPROMPT_REGISTER_END(g_voicePrompt);

                HUD::_UIPROMPT_SET_VISIBLE(g_voicePrompt, true);
                HUD::_UIPROMPT_SET_ENABLED(g_voicePrompt, true);
            }
        }
    }
}

// --- Main Script Interaction Loop ---
bool bWasInteracting = false;
Ped currentTargetPed = 0;

void update()
{
    Ped playerPed = PLAYER::PLAYER_PED_ID();
    if (!ENTITY::DOES_ENTITY_EXIST(playerPed)) return;

    // Safety: Ensure Arthur is always unmuted so dialogue prompts remain active
    AUDIO::STOP_PED_SPEAKING(playerPed, false);

    // Handle turning off the native busy spinner
    if (g_bTurnOffSpinner)
    {
        HUD::BUSYSPINNER_OFF();
        g_bTurnOffSpinner = false;
        g_busySpinnerExpireTime = 0;
    }
    if (g_busySpinnerExpireTime > 0 && GetTickCount() > g_busySpinnerExpireTime)
    {
        HUD::BUSYSPINNER_OFF();
        g_busySpinnerExpireTime = 0;
    }

    // 1. Detect targeted NPC
    Entity targetEntity = 0;
    Player player = PLAYER::PLAYER_ID();

    if (!PLAYER::GET_PLAYER_TARGET_ENTITY(player, &targetEntity))
    {
        PLAYER::GET_ENTITY_PLAYER_IS_FREE_AIMING_AT(player, &targetEntity);
    }

    // Only update target ped if a valid living human NPC exists; clear if not targeting
    if (ENTITY::DOES_ENTITY_EXIST(targetEntity) && 
        ENTITY::IS_ENTITY_A_PED(targetEntity) && 
        !ENTITY::IS_ENTITY_DEAD(targetEntity) &&
        (Ped)targetEntity != playerPed &&
        !PED::IS_PED_A_PLAYER((Ped)targetEntity) &&
        PED::IS_PED_HUMAN((Ped)targetEntity))
    {
        currentTargetPed = (Ped)targetEntity;
    }
    else if (!bWasInteracting)
    {
        currentTargetPed = 0;
    }

    // Dedicated Voice Push-to-Talk: Keyboard 'T'
    bool isTKey = (GetAsyncKeyState('T') & 0x8000) != 0;

    // Dedicated Voice Push-to-Talk: Controller 'A' (Cross on PS)
    bool isControllerA = IsControllerAPressed() ||
                         IsActionDown(0xD10A3A36); // INPUT_INTERACT_LOCKON_A

    if (g_voicePrompt != 0 && HUD::_UIPROMPT_IS_VALID(g_voicePrompt))
    {
        if (HUD::_UIPROMPT_IS_PRESSED(g_voicePrompt) || HUD::_UIPROMPT_IS_HOLD_MODE_RUNNING(g_voicePrompt))
        {
            isControllerA = true;
        }
    }

    // Update native bottom-right prompt UI attached to the targeted ped
    UpdateVoicePrompt(currentTargetPed);

    // Voice interaction only triggers on A (Controller) or T (Keyboard) while locked on
    // Vanilla Greet (X / R), Antagonize (B / F), and Rob (Y / E) are 100% untouched!
    bool isInteracting = (isControllerA || isTKey) && (currentTargetPed != 0);

    // When voice interacting, suppress jumping/sprinting
    if (isInteracting)
    {
        DisableAction(0xD10A3A36); // INPUT_INTERACT_LOCKON_A
        DisableAction(0xD70300FA); // INPUT_JUMP
        DisableAction(0x8FF9C51F); // INPUT_SPRINT

        AUDIO::STOP_CURRENT_PLAYING_SPEECH(playerPed, 0);
        AUDIO::STOP_CURRENT_PLAYING_AMBIENT_SPEECH(playerPed, 0);
    }

    // Interaction Started (Button Just Pressed)
    if (isInteracting && !bWasInteracting && currentTargetPed != 0)
    {
        bWasInteracting = true;

        // Suppress Arthur's canned voice lines
        AUDIO::STOP_CURRENT_PLAYING_SPEECH(playerPed, 0);
        AUDIO::STOP_CURRENT_PLAYING_AMBIENT_SPEECH(playerPed, 0);

        // Turn NPC to face Arthur
        TASK::TASK_TURN_PED_TO_FACE_ENTITY(currentTargetPed, playerPed, 4000, 0.0f, 0.0f, 0.0f);

        // Extract metadata from the targeted NPC
        bool isMale = (PED::IS_PED_MALE(currentTargetPed) != 0);
        Hash modelHash = ENTITY::GET_ENTITY_MODEL(currentTargetPed);
        Vector3 coords = ENTITY::GET_ENTITY_COORDS(currentTargetPed, true, false);
        Vector3 playerCoords = ENTITY::GET_ENTITY_COORDS(playerPed, true, false);
        Hash zoneHash = ZONE::_GET_MAP_ZONE_AT_COORDS(coords.x, coords.y, coords.z, 10);
        
        float distance = MISC::GET_DISTANCE_BETWEEN_COORDS(coords.x, coords.y, coords.z, playerCoords.x, playerCoords.y, playerCoords.z, true);

        Entity aimedEntity = 0;
        bool isPlayerAiming = (PLAYER::GET_ENTITY_PLAYER_IS_FREE_AIMING_AT(player, &aimedEntity) != 0) && (aimedEntity == (Entity)currentTargetPed);

        bool isMounted = (PED::IS_PED_ON_MOUNT(currentTargetPed) != 0);
        bool inVehicle = (PED::IS_PED_IN_ANY_VEHICLE(currentTargetPed, false) != 0);
        bool isHogtied = (PED::_IS_PED_HOGTIED(currentTargetPed) != 0);
        bool isInjured = (PED::IS_PED_INJURED(currentTargetPed) != 0);
        bool isUsingScenario = (PED::IS_PED_USING_ANY_SCENARIO(currentTargetPed) != 0);
        bool isIndoors = (INTERIOR::GET_INTERIOR_FROM_ENTITY(currentTargetPed) != 0);
        bool isRaining = (MISC::GET_RAIN_LEVEL() > 0.15f);
        bool isSnowing = (MISC::GET_SNOW_LEVEL() > 0.15f);
        bool isArthurMounted = (PED::IS_PED_ON_MOUNT(playerPed) != 0);
        int wantedLevel = PLAYER::GET_PLAYER_WANTED_LEVEL(player);
        Hash relGroup = PED::GET_PED_RELATIONSHIP_GROUP_HASH(currentTargetPed);

        Hash weaponHash = 0;
        bool isArmed = (WEAPON::GET_CURRENT_PED_WEAPON(currentTargetPed, &weaponHash, true, 0, false) != 0) 
                       && (weaponHash != MISC::GET_HASH_KEY("WEAPON_UNARMED")) 
                       && (weaponHash != 0);

        bool isCombat = (PED::IS_PED_IN_COMBAT(currentTargetPed, 0) != 0);
        bool isFleeing = (PED::IS_PED_FLEEING(currentTargetPed) != 0);
        int hour = CLOCK::GET_CLOCK_HOURS();
        int health = ENTITY::GET_ENTITY_HEALTH(currentTargetPed);

        std::string mode = "talk";

        // Build JSON event string
        std::stringstream ss;
        ss << "{"
           << "\"event\":\"START_TALK\","
           << "\"pedId\":" << currentTargetPed << ","
           << "\"isMale\":" << (isMale ? "true" : "false") << ","
           << "\"model\":" << modelHash << ","
           << "\"zone\":" << zoneHash << ","
           << "\"isArmed\":" << (isArmed ? "true" : "false") << ","
           << "\"isCombat\":" << (isCombat ? "true" : "false") << ","
           << "\"isFleeing\":" << (isFleeing ? "true" : "false") << ","
           << "\"isHogtied\":" << (isHogtied ? "true" : "false") << ","
           << "\"isMounted\":" << (isMounted ? "true" : "false") << ","
           << "\"inVehicle\":" << (inVehicle ? "true" : "false") << ","
           << "\"isInjured\":" << (isInjured ? "true" : "false") << ","
           << "\"isUsingScenario\":" << (isUsingScenario ? "true" : "false") << ","
           << "\"isIndoors\":" << (isIndoors ? "true" : "false") << ","
           << "\"isRaining\":" << (isRaining ? "true" : "false") << ","
           << "\"isSnowing\":" << (isSnowing ? "true" : "false") << ","
           << "\"isArthurMounted\":" << (isArthurMounted ? "true" : "false") << ","
           << "\"isPlayerAiming\":" << (isPlayerAiming ? "true" : "false") << ","
           << "\"wantedLevel\":" << wantedLevel << ","
           << "\"distance\":" << distance << ","
           << "\"relGroup\":" << relGroup << ","
           << "\"hour\":" << hour << ","
           << "\"health\":" << health << ","
           << "\"mode\":\"" << mode << "\""
           << "}";

        EnqueueMessage(ss.str());
    }
    // Interaction Ongoing (Holding button)
    else if (isInteracting && bWasInteracting)
    {
        AUDIO::STOP_CURRENT_PLAYING_SPEECH(playerPed, 0);

        // Show clean Top-Left help indicator while holding button
        DrawTopLeftHelp("~COLOR_YELLOW~[MIC]~s~ Listening... Speak into microphone");
    }
    // Interaction Stopped (Button Released)
    else if (!isInteracting && bWasInteracting)
    {
        bWasInteracting = false;
        EnqueueMessage("{\"event\":\"STOP_TALK\"}");

        // Ensure Arthur remains unmuted
        AUDIO::STOP_PED_SPEAKING(playerPed, false);

        // Native UI: Show RDR2's authentic Revolver Busy Spinner in bottom-right corner!
        const char* spinnerText = MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", "Thinking...");
        HUD::_BUSYSPINNER_SET_TEXT(spinnerText);
        g_busySpinnerExpireTime = GetTickCount() + 10000; // 10s auto-safety timeout
    }
    // Locked onto an NPC: guide the player
    else if (currentTargetPed != 0 && !bWasInteracting)
    {
        DrawTopLeftHelp("Hold ~COLOR_YELLOW~[A]~s~ or ~COLOR_YELLOW~[T]~s~ to speak into mic");
    }

    // 3. Render dialogue subtitles only for real NPC speech
    {
        std::lock_guard<std::mutex> lock(g_netMutex);
        if (GetTickCount() < g_subtitleExpireTime && !g_currentSubtitle.empty())
        {
            DrawDialogueSubtitle(g_currentSpeaker, g_currentSubtitle, g_currentTranscription);
        }
    }
}

void main()
{
    std::thread netThread(NetworkWorker);
    netThread.detach();

    while (true)
    {
        update();
        WAIT(0);
    }
}

void ScriptMain()
{
    main();
}

BOOL APIENTRY DllMain(HMODULE hInstance, DWORD reason, LPVOID lpReserved)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        scriptRegister(hInstance, ScriptMain);
        break;
    case DLL_PROCESS_DETACH:
        g_bNetRunning = false;
        HUD::BUSYSPINNER_OFF();
        scriptUnregister(hInstance);
        break;
    }
    return TRUE;
}
