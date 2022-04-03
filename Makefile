.PHONY: help get-aws-params debug debug-rebuild debug-stop debug-vscode prune check-aws-credentials check-vpn-connected
.DEFAULT_GOAL := help
help:
	@grep -E '(^[a-zA-Z_-]+:.*?##.*$$)|(^##)' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}{printf "\033[32m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\[32m##/[33m/'

aws-session-token = $(AWS_SESSION_TOKEN)
aws-secret-access-key=$(AWS_SECRET_ACCESS_KEY)
aws-access-key-id=$(AWS_ACCESS_KEY_ID)
customer=$(customer)
environment=$(environment)
client-name=$(client)

debug: get-aws-params ## 🛠 setup the flask Docker container, install the requirements...
	@docker-compose up
	@rm -f .env

debug-rebuild: prune get-aws-params ## 🛠  setup the flask Docker container with rebuild, install the requirements...
	@docker-compose up
	@rm -rf .env

debug-vscode: get-aws-params check-vpn-connected ## write env file for use by vscode 🛠
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) environment variables for customer ${customer} have been set locally to dev-environment/.env
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) associate vscode with an python environment and load the requirements.txt
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) with pip install -r requirements.txt and
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) then run the vscode debug profile 'Python: Flask'

debug-pycharm: get-aws-params check-vpn-connected ## write env file for use by pycharm
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) environment variables for customer ${customer} have been set locally to dev-environment/.env
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) load the pycharm plugin from https://github.com/Ashald/EnvFile 
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) associate pycharm with an python environment and load the requirements.txt
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) "with 'pip install -r requirements.txt' and"
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) then run the config pycharm to load the .env file. Next, run pycharm debugger.

debug-stop: ## 🛠  stop docker compose
	@docker-compose down
	@rm -f .env

prune: ## Purge all docker builds and related files
	@docker system prune -f -a

get-aws-params: check-aws-credentials #buildEnv.bat
# see https://github.com/springload/ssm-parent for more info
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) getting aws paramaters for customer $(customer)
	@rm -f .vscode/.env
	@AWS_DEFAULT_REGION=us-east-1 ENVIRONMENT=$(environment) ssm-parent dotenv .vscode/.env -c ssm-parent.json


check-aws-credentials:
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) "checking for temporary aws credentials"
ifneq ("$(aws-session-token)","")
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) "aws temporary credentials were found."
else
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) "aws temporary credentials were not found.  you must load temporary AWS credentials"
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) "before running this makescript. see tab 'sso manual' at:"
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) "https://humahq.stoplight.io/docs/huma-platform/docs/1%20-%20General/Accessing%20Environments.md"
	@exit 1
endif

check-vpn-connected:
	@echo $$(gdate +%Y/%m/%d_%H:%M:%S) checking vpn connection status
	@timeout --preserve-status 5 nc -z -w 1 postgres.huma.local 5432 || exit -1

##Before runnning this script, you should obtain temporary AWS credentials
##and connect to the VPN for a given customer.  
##See https://humahq.stoplight.io/docs/huma-platform/docs/1%20-%20General/Accessing%20Environments.md
##-----
##Usage: 'make COMMAND customer=XXX'
