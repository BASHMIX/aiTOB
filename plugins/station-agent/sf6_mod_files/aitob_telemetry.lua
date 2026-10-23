-- ==============================================================================
-- aiTOB Station Agent - Street Fighter 6 Telemetry v20 (Room Info Fix)
-- File: aitob_telemetry.lua
-- Place in: <SF6_ROOT>/reframework/autorun/aitob_telemetry.lua
-- ==============================================================================

local socket_ok, socket = pcall(require, "socket")

local config = {
    destination_ip            = "127.0.0.1",
    destination_port          = 8080,
    heartbeat_interval_frames = 60,
    enable_debug_overlay      = true,
    rounds_to_win             = 2,
}

local SF6_CHAR_NAMES = {
    [1]="Ryu", 
    [2]="Luke", 
    [3]="Kimberly", 
    [4]="Chun-Li", 
    [5]="Manon",
    [6]="Zangief", 
    [7]="JP", 
    [8]="Dhalsim", 
    [9]="Cammy", 
    [10]="Ken",
    [11]="Dee Jay", 
    [12]="Lily", 
    [13]="A.K.I.", 
    [14]="Rashid", 
    [15]="Blanka",
    [16]="Juri", 
    [17]="Marisa", 
    [18]="Guile", 
    [19]="ED", 
    [20]="E. Honda",
    [21]="Jamie", 
    [22]="Akuma",
    [25]="Sagat", 
    [26]="M. Bison", 
    [27]="Terry", 
    [28]="Mai", 
    [29]="Elena", 
    [30]="C. Viper",
    [31]="Alex",
    [32]="Ingrid",
    [33]="Yasmine",
    [34]="Arjun",
    [35]="Bosch",
    [36]="Tifa Lockhart"
}

local SF6_STAGE_NAMES = {
    [0]="Colosseo",[1]="Carrier Byron Taylor",[2]="Dhalsimer Temple",
    [3]="Old Town Market",[4]="Genbu Temple",[5]="Thunderfoot Settlement",
    [6]="Suval'hal Arena",[7]="Macho Ring",[8]="Fete Foraine",
    [9]="Training Room",[10]="Ranger's Hut",[11]="Metro City Downtown",
    [12]="Bathers Beach",[13]="Bathers Beach Night",[14]="Barmaley Steelworks",
    [15]="Ruined Lab", [16]="Enma's Hollow", [17]="Pao Pao Cafe 6",
}

local state = {
    udp = nil, is_connected = false, packets_sent = 0, last_error = nil,
    frame_count = 0,
    screen = "UNKNOWN", match_state = "IDLE",
    p1 = { char_id=0, char_name="None", hp=10000, max_hp=10000, rounds=0, game_wins=0, combos=0, dmg=0, drive=60000, super=0 },
    p2 = { char_id=0, char_name="None", hp=10000, max_hp=10000, rounds=0, game_wins=0, combos=0, dmg=0, drive=60000, super=0 },
    round_timer = 99, stage_no = -1, stage_name = "---", fight_st = 0, room_id = ""
}

local last_event_hash = ""
local cached_crm_fields = false
local crm_room_id_field = nil
local crm_p1_streak_field = nil
local crm_p2_streak_field = nil

local function to_json(val)
    local t=type(val)
    if t=="table" then
        local parts={}
        for k,v in pairs(val) do table.insert(parts,string.format("%q:%s",tostring(k),to_json(v))) end
        return "{"..table.concat(parts,",").."}"
    elseif t=="string" then return string.format("%q",val)
    elseif t=="number" or t=="boolean" then return tostring(val)
    else return "null" end
end

local function init_socket()
    if not socket_ok then state.last_error = "LuaSocket not installed"; return false end
    local ok, udp = pcall(function()
        local u = socket.udp(); u:settimeout(0)
        u:setpeername(config.destination_ip, config.destination_port)
        return u
    end)
    if ok and udp then state.udp = udp; state.is_connected = true; state.last_error = nil; return true end
    state.is_connected = false; state.last_error = "UDP error"; return false
end

local function send_telemetry(payload)
    if json and json.dump_file then pcall(function() json.dump_file("aitob_telemetry.json", payload) end) end
    if state.udp then pcall(function() state.udp:send(to_json(payload)) end) end
    state.packets_sent = state.packets_sent + 1
end

local function read_game_state()
    local ctx = { gBattle = nil, sGame = nil, sSetting = nil, cPlayer = nil, cTeam = nil }
    if sdk then
        local gB = sdk.find_type_definition("gBattle")
        if gB then
            ctx.gBattle = gB
            pcall(function()
                local function gf(n) local f = gB:get_field(n); return f and f:get_data(nil) or nil end
                ctx.sGame = gf("Game"); ctx.sSetting = gf("Setting"); 
                local sPlayer = gf("Player"); ctx.cPlayer = sPlayer and sPlayer.mcPlayer or nil
                local sTeam = gf("Team"); ctx.cTeam = sTeam and sTeam.mcTeam or nil
            end)
        end
    end

    local id1, id2 = state.p1.char_id, state.p2.char_id
    local stage_no, stage_name = state.stage_no, state.stage_name

    if ctx.sSetting then
        pcall(function()
            if ctx.sSetting.TeamData then
                local p1_type = ctx.sSetting.TeamData[0].PlayerData[0].PlayerType
                local p2_type = ctx.sSetting.TeamData[1].PlayerData[0].PlayerType
                if type(p1_type)=="number" and p1_type>0 then id1 = p1_type end
                if type(p2_type)=="number" and p2_type>0 then id2 = p2_type end
            end
            if ctx.sSetting.StageNo ~= nil then
                stage_no = ctx.sSetting.StageNo
                stage_name = SF6_STAGE_NAMES[stage_no] or ("Stage ID: " .. tostring(stage_no))
            end
        end)
    end
    
    if id1 == nil or id1 == 0 then id1 = 1 end
    if id2 == nil or id2 == 0 then id2 = 19 end

    local fight_st = 0
    local timer = 99
    if ctx.sGame then
        pcall(function()
            if ctx.sGame.fight_st ~= nil then fight_st = ctx.sGame.fight_st end
            if ctx.sGame.stage_timer ~= nil then timer = math.max(0, math.floor(ctx.sGame.stage_timer / 60)) end
        end)
    end

    local p1hp, p2hp, p1max, p2max, p1drive, p2drive = 0, 0, 10000, 10000, 60000, 60000
    if ctx.cPlayer then
        pcall(function() 
            local p1 = ctx.cPlayer[0]
            if p1 then
                p1hp = math.max(0, math.floor(tonumber(tostring(p1.vital_new)) or 0))
                p1max = math.floor(tonumber(tostring(p1.vital_max)) or 10000)
                p1drive = math.floor(tonumber(tostring(p1.focus_new)) or 0)
            end
            local p2 = ctx.cPlayer[1]
            if p2 then
                p2hp = math.max(0, math.floor(tonumber(tostring(p2.vital_new)) or 0))
                p2max = math.floor(tonumber(tostring(p2.vital_max)) or 10000)
                p2drive = math.floor(tonumber(tostring(p2.focus_new)) or 0)
            end
        end)
    end
    
    local p1wins, p2wins, p1dmg, p2dmg, p1comb, p2comb, p1super, p2super = 0, 0, 0, 0, 0, 0, 0, 0
    if ctx.cTeam then
        pcall(function() 
            local t1, t2 = ctx.cTeam[0], ctx.cTeam[1]
            if t1 then p1wins = t1.mWinCount; p1dmg = t1.mMaxDamage; p1comb = t1.mComboCount; p1super = tonumber(tostring(t1.mSuperGauge)) or 0 end
            if t2 then p2wins = t2.mWinCount; p2dmg = t2.mMaxDamage; p2comb = t2.mComboCount; p2super = tonumber(tostring(t2.mSuperGauge)) or 0 end
        end)
    end

    local p1gwins, p2gwins, room_id = 0, 0, ""
    pcall(function()
        local crm = sdk.get_managed_singleton("app.CustomRoomManager")
        if crm then
            if not cached_crm_fields then
                local td = crm:get_type_definition()
                for _, f in ipairs(td:get_fields()) do
                    local fname = f:get_name()
                    if fname == "<CustomRoomRoomId>k__BackingField" or fname == "CustomRoomRoomId" or fname == "RoomId" then crm_room_id_field = f
                    elseif fname == "P1WinStreak" then crm_p1_streak_field = f
                    elseif fname == "P2WinStreak" then crm_p2_streak_field = f end
                end
                cached_crm_fields = true
            end
            
            if crm_room_id_field then
                local val = crm_room_id_field:get_data(crm)
                if type(val) == "string" then room_id = val
                elseif val then pcall(function() room_id = val:get_data() or tostring(val) end) end
            end
            if crm_p1_streak_field then p1gwins = crm_p1_streak_field:get_data(crm) or 0 end
            if crm_p2_streak_field then p2gwins = crm_p2_streak_field:get_data(crm) or 0 end
        end
    end)
    if type(room_id) ~= "string" then room_id = "" end

    local ms = "IDLE"
    local screen = "MAIN_MENU_OR_IDLE"
    
    if fight_st == 0 then
        ms = "IDLE"
        if room_id ~= "" then
            screen = "CUSTOM_ROOM_LOBBY"
        else
            screen = "CHARACTER_SELECT_OR_MENU"
        end
    elseif fight_st == 5 then 
        ms = "ROUND_OVER"
        screen = "MATCH_RESULTS"
    elseif fight_st >= 1 and fight_st <= 4 then 
        ms = "FIGHTING"
        screen = "FIGHTING"
    end

    local n1 = SF6_CHAR_NAMES[id1] or ("Unknown ID: " .. tostring(id1))
    local n2 = SF6_CHAR_NAMES[id2] or ("Unknown ID: " .. tostring(id2))

    return {
        game = "SF6", screen = screen, match_state = ms, round_timer = timer, fight_st = fight_st,
        room_id = room_id,
        stage = { no = stage_no, name = stage_name },
        p1 = { character_id = id1, character_name = n1, current_hp = p1hp, max_hp = p1max, rounds_won = p1wins, game_wins = p1gwins, max_combo = p1comb, max_damage = p1dmg, drive_gauge = (p1drive / 10000.0), super_art = math.floor(p1super / 10000.0) },
        p2 = { character_id = id2, character_name = n2, current_hp = p2hp, max_hp = p2max, rounds_won = p2wins, game_wins = p2gwins, max_combo = p2comb, max_damage = p2dmg, drive_gauge = (p2drive / 10000.0), super_art = math.floor(p2super / 10000.0) },
        debug = { is_connected = state.is_connected, last_error = state.last_error or "none", socket_ok = socket_ok }
    }
end

if re and re.on_frame then
    re.on_frame(function()
        state.frame_count = state.frame_count + 1
        local t = read_game_state()
        if not t then return end
        
        state.screen = t.screen; state.match_state = t.match_state; state.room_id = t.room_id
        state.p1.char_name = t.p1.character_name; state.p2.char_name = t.p2.character_name
        state.p1.char_id = t.p1.character_id; state.p2.char_id = t.p2.character_id
        state.p1.hp = t.p1.current_hp; state.p2.hp = t.p2.current_hp
        state.p1.max_hp = t.p1.max_hp; state.p2.max_hp = t.p2.max_hp
        state.p1.rounds = t.p1.rounds_won; state.p2.rounds = t.p2.rounds_won
        state.p1.game_wins = t.p1.game_wins; state.p2.game_wins = t.p2.game_wins
        state.p1.dmg = t.p1.max_damage; state.p2.dmg = t.p2.max_damage
        state.p1.combos = t.p1.max_combo; state.p2.combos = t.p2.max_combo
        state.stage_name = t.stage.name; state.round_timer = t.round_timer
        
        local current_event_hash = string.format("%d_%d_%d_%d_%s_%d_%d_%d_%d_%d", t.p1.character_id, t.p2.character_id, t.p1.rounds_won, t.p2.rounds_won, t.screen, t.p1.current_hp, t.p2.current_hp, t.p1.drive_gauge, t.p2.drive_gauge, t.round_timer)
        if (current_event_hash ~= last_event_hash) or (state.frame_count % config.heartbeat_interval_frames == 0) then
            last_event_hash = current_event_hash
            send_telemetry(t)
        end
    end)
end

if re and re.on_draw_ui then
    re.on_draw_ui(function()
        if not config.enable_debug_overlay then return end
        if imgui.tree_node("aiTOB Station Telemetry (v20 - Room Fix)") then
            imgui.text_colored("--- [ MATCH STATUS ] ---", 0xFF00FF00)
            imgui.text(string.format("Screen: %s", state.screen))
            if state.room_id ~= "" then imgui.text_colored("Room ID: " .. state.room_id, 0xFFFF00FF) end
            imgui.text(string.format("Match State: %s | Timer: %d", state.match_state, state.round_timer))
            imgui.text(string.format("Stage: %s (ID: %d)", state.stage_name, state.stage_no))
            imgui.text(string.format("Game Wins (Streak): P1: %d  |  P2: %d", state.p1.game_wins, state.p2.game_wins))
            imgui.separator()

            imgui.text_colored("--- [ PLAYERS ] ---", 0xFFFFFF00)
            imgui.text(string.format("P1 [%s] (ID:%d)", state.p1.char_name, state.p1.char_id))
            imgui.text(string.format("  HP: %d/%d | Rounds: %d", state.p1.hp, state.p1.max_hp, state.p1.rounds))
            imgui.text(string.format("  Max Combo: %d | Max DMG: %d", state.p1.combos, state.p1.dmg))
            imgui.separator()
            imgui.text(string.format("P2 [%s] (ID:%d)", state.p2.char_name, state.p2.char_id))
            imgui.text(string.format("  HP: %d/%d | Rounds: %d", state.p2.hp, state.p2.max_hp, state.p2.rounds))
            imgui.text(string.format("  Max Combo: %d | Max DMG: %d", state.p2.combos, state.p2.dmg))
            imgui.tree_pop()
        end
    end)
end

init_socket()
