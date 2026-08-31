-- LUA004: valid Lua, but nothing is exported, so TaCZ loads an empty module
-- and every hook silently does nothing.
local M = {}

function M.shoot(api)
    api:shootOnce(api:isShootingNeedConsumeAmmo())
end
