-- LUA005: luapack_missing_module names this pack's namespace, but there is no
-- such script in it. require("tacz_default_state_machine") on the next line is
-- fine: tacz is the mod's own namespace, supplied from outside the pack.
local missing = require("luapack_missing_module")
local default = require("tacz_default_state_machine")

local M = {
    missing = missing,
    default = default
}

return M
