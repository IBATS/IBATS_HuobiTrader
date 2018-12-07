@echo off
del /Q .\dist\*
python setup.py sdist bdist_wheel
rd /S /Q .\build
@echo on
