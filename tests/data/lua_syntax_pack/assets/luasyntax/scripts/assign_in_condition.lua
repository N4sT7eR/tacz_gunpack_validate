local M = {}

function M.shoot(api)
    local mode = api:getFireMode()
    if mode = AUTO then
        api:shootOnce(true)
    end
end

return M
