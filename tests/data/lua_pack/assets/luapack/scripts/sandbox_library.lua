-- LUA003: TaCZ installs base, package, table, string, math and bit32 only.
-- os and io are nil here, so both of these crash the moment they run.
local M = {}

function M.stamp()
    local now = os.time()
    io.write(tostring(now))
    return now
end

return M
