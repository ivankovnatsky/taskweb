.PHONY: dev serve test format clean bump release update

dev:
	nix develop

serve:
	python -m taskweb serve

test:
	pytest -v

format:
	ruff format .
	ruff check --fix .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf dist build .pytest_cache .coverage htmlcov

update:
	nix flake update

bump:
	@current=$$(grep 'version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/'); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	patch=$$(echo $$current | cut -d. -f3); \
	new_patch=$$((patch + 1)); \
	new_version="$$major.$$minor.$$new_patch"; \
	sed -i "s/version = \"$$current\"/version = \"$$new_version\"/" pyproject.toml; \
	echo "Bumped version: $$current -> $$new_version"

release: bump
	@version=$$(grep 'version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/'); \
	git add pyproject.toml; \
	git commit -m "Bump version to $$version"; \
	git tag "v$$version"; \
	git push origin main --tags; \
	gh release create "v$$version" --generate-notes
