"""Project configuration for `sillo-start`.

Read by the CLI so `add`, `dev`, `doctor`, `generate` and `migrate` know what
this project is. The application never imports this file — its own settings
come from the environment, via `app/config.py`.

`queue` and `scheduler` are absent on purpose: the code is present but the
wiring is commented out in `app/bootstrap.py`. Add them here when you switch
it on, so `sillo-start dev` starts the worker alongside the app.
"""

package = 'starter'
features = [
    'database',
    'auth',
    'admin',
    'session',
    'api',
]
auth_strategy = 'session'
admin_title = 'Starter Admin'
