local M = {}

function M.shoot(api)
    if api:getFireMode() != AUTO then
        api:shootOnce(true)
    end
end

return M
