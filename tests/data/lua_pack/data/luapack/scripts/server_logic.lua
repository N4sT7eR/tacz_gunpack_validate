-- Clean server-side logic, so the data/ half of the search is covered by a
-- file that must produce nothing rather than only by ones that must fail.
local M = {}

function M.shoot(api)
    api:shootOnce(api:isShootingNeedConsumeAmmo())
end

function M.tick_reload(api)
    local params = api:getScriptParams()
    if params == nil then
        return NOT_RELOADING, -1
    end
    return TACTICAL_RELOAD_FEEDING, params.loop * 1000 - api:getReloadTime()
end

return M
