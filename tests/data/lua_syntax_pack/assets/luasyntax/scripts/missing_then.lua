local M = {}

function M.shoot(api)
    if api:getAmmoAmount() > 0
        api:shootOnce(true)
    end
end

return M
