-- No findings. Exercises the constructs that must NOT be reported: method
-- definitions and their implicit self, loop variables, table keys that happen
-- to share a name with nothing, field access, and every injected constant.
local default = require("tacz_default_state_machine")
local STATIC_TRACK_LINE = default.STATIC_TRACK_LINE
local MAIN_TRACK = default.MAIN_TRACK

local idle_state = {
    name = "idle"
}

function idle_state.entry(this, context)
    local track = context:getTrack(STATIC_TRACK_LINE, MAIN_TRACK)
    context:runAnimation("static_idle", track, true, LOOP, 0)
end

function idle_state.transition(this, context, input)
    if input == INPUT_SHOOT then
        return nil
    end
    if input == INPUT_RELOAD and context:getAmmoCount() > 0 then
        return nil
    end
    for index = 1, 3 do
        if context:isStopped(index) then
            context:stopAnimation(index)
        end
    end
    for key, value in pairs(idle_state) do
        if type(value) == "string" then
            print(key, math.min(#value, 8))
        end
    end
    return nil
end

local M = setmetatable({
    idle_state = idle_state
}, {__index = default})

function M:states()
    return { self.idle_state }
end

function M:initialize(context)
    default.initialize(self, context)
end

return M
