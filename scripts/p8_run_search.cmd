@echo off
REM Prompt 8 Part 2: the search at native cadence over the whole P8 population.
REM   %1 = concurrency, %2 = config (survey_p8 or survey_p8_600s, per the 600-s decision)
REM Prefetch (the prepared-series cache from the audit store, no MAST) at 8 workers, then the search
REM with --resume; a second --resume pass retries anything that errored.  Rerun to continue after a kill.
set REPO=C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter
set PY=C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe
set LIGHTKURVE_CACHE=%REPO%\data\cache\lightkurve
set PYTHONIOENCODING=utf-8
cd /d %REPO%
echo === prefetch %2 === %date% %time%
%PY% scripts\run_survey.py --targets data\survey\targets_p8.csv --config %2 --out data\survey\runs\p8_prefetch --prefetch --concurrency 8 --timeout 900 --resume
if %errorlevel% neq 0 echo prefetch orchestrator exit %errorlevel%
echo === search %2 === %date% %time%
%PY% scripts\run_survey.py --targets data\survey\targets_p8.csv --config %2 --out data\survey\runs\survey_p8 --concurrency %1 --timeout 1500 --resume
if %errorlevel% neq 0 echo search orchestrator exit %errorlevel%
echo === retry pass === %date% %time%
%PY% scripts\run_survey.py --targets data\survey\targets_p8.csv --config %2 --out data\survey\runs\survey_p8 --concurrency %1 --timeout 1500 --resume --retries 2
if %errorlevel% neq 0 echo retry orchestrator exit %errorlevel%
echo === DONE search === %date% %time%
