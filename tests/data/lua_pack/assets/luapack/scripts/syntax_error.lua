-- LUA001: the call to shootOnce is never closed, so the chunk does not parse.
local M = {}

function M.shoot(api)
    api:shootOnce(true
end

return M
