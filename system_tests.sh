#!/bin/bash
echo
echo "---- start huma cli smoke tests with autostart and autostop of system services   ----"
echo huma smoke-tests --input-file ./smoke_test_config_sample.json -f True
huma smoke-tests --input-file ./smoke_test_config_sample.json -f True
echo "---- end of huma cli smoke-tests -----"
echo

exit 0