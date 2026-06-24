.PHONY: fmt validate test lint security all package

all: fmt validate lint test security

fmt:
	terraform fmt -recursive

validate:
	powershell -ExecutionPolicy Bypass -File ./scripts/validate.ps1

lint:
	tflint --recursive

test:
	cd lambda_src && go test ./...

security:
	trivy config .
	checkov -d . --framework terraform

package:
	powershell -ExecutionPolicy Bypass -File ./scripts/package-lambdas.ps1
