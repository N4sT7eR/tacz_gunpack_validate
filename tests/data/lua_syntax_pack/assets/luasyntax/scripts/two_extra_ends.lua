-- Two spare "end" keywords, in different functions. The parser stops at the
-- first token it cannot place, so the second is only found by stepping over
-- the first -- which is what its own advice, "remove this", describes.
local M = {}

function M.shoot(api)
    api:shootOnce(true)
end
end

function M.reload(api)
    api:putAmmoInMagazine(1)
end
end

return M
