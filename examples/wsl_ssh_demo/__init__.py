"""wsl_ssh_demo — run two tiny Operations on a remote WSL box via SSH.

Capabilities registered
-----------------------
    add_two   x -> x + 2     (scripts/add_two.py)
    cube      x -> x ** 3    (scripts/cube.py)

Workflow:  add_two_then_cube   result = (x + 2) ** 3
Planner:   wsl_ssh_add_cube_optuna  (Optuna TPE, maximise, x in [0, 10])

Apply with:  pixi run apply-bootstrap -- wsl_ssh_demo
"""
