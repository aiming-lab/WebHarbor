#!/bin/bash
cd "$(dirname "$0")/.."
rm -rf instance
cp -r instance_seed instance
exec env WEBSYN_SKIP_BOOTSTRAP=1 python3.11 -c "from app import app; app.jinja_env.auto_reload = True; app.run(host='0.0.0.0', port=46093, debug=False, threaded=True)"
