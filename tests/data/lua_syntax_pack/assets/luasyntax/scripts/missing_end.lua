local M = {}

function M.shoot(api)
    if api:hasAmmoInBarrel() then
        api:shootOnce(true)
end

return M
