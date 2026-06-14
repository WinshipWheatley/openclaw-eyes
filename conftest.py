"""Repository-level pytest collection rules."""

# Archived planning docs contain copied historical test files with names that
# collide with canonical tests under ./tests. Keep full-suite collection on live
# tests and ignore docs as artifacts.
collect_ignore = ["test_effect_adapters.py"]
collect_ignore_glob = ["docs/**"]
