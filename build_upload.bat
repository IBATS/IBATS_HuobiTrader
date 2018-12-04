@echo off
del /Q .\dist\*
python setup.py sdist bdist_wheel
rd /S /Q .\build
::twine upload -u mmmaaaggg -p pypi13172115 dist/*
@echo on
