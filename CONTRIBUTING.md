# Monorepo git safety
#
# This repository (QuadrantHR) is the ONLY git remote we push to.
# Team folders (EmployeeDirectory, Ticket-Genie, ClosedAI, etc.) are vendored
# snapshots — their nested .git directories were removed so they cannot be
# pushed back to other teams' GitHub repos by accident.
#
# Remotes:
#   origin            → https://github.com/IsheteDGr8/QuadrantHR.git
#   quadrant-legacy   → old stub (do not use for day-to-day work)
#
# Never re-add a .git folder inside a module directory. Prefer new work under
# portal/ and gateway/ rather than editing team apps when possible.
