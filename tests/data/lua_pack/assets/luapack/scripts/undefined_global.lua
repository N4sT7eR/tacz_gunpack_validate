-- LUA002: PLAY_ONCE_STPO is a typo for PLAY_ONCE_STOP, and FIRE_MODE_TRACK is
-- never declared -- the same mistake the official deagle script makes. Lua
-- reads both as nil rather than failing, so only a checker catches them.
local default = require("tacz_default_state_machine")
local STATIC_TRACK_LINE = default.STATIC_TRACK_LINE

local idle_state = {}

function idle_state.update(this, context)
    local track = context:getTrack(STATIC_TRACK_LINE, FIRE_MODE_TRACK)
    context:runAnimation("idle", track, true, PLAY_ONCE_STPO, 0)
end

local M = {
    idle_state = idle_state
}

return M
