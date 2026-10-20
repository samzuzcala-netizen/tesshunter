@echo off
REM Prompt 8 Part 1e: the injection run, the false-alarm run and the 600-second comparison, in sequence.
REM Every stage is checkpointed by run_survey.py (--resume); rerun this file to continue after a kill.
set REPO=C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter
set PY=C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe
set LIGHTKURVE_CACHE=%REPO%\data\cache\lightkurve
set PYTHONIOENCODING=utf-8
cd /d %REPO%
echo === injections (survey_p8) === %date% %time%
%PY% scripts\run_survey.py --injections data\survey\injections_p8.csv --config survey_p8 --out data\survey\runs\inj_p8 --concurrency %1 --timeout 1500 --resume
if %errorlevel% neq 0 echo injections orchestrator exit %errorlevel%
echo === false alarms (survey_p8) === %date% %time%
%PY% scripts\run_survey.py --sample data\survey\completeness_sample_p8.csv --config survey_p8 --out data\survey\runs\fa_p8 --concurrency %1 --timeout 1500 --resume
if %errorlevel% neq 0 echo false-alarm orchestrator exit %errorlevel%
echo === 600-s comparison (survey_p8_600s, 100-star subset) === %date% %time%
%PY% scripts\run_survey.py --injections data\survey\injections_p8_600s_subset.csv --config survey_p8_600s --out data\survey\runs\inj_p8_600s --concurrency %1 --timeout 1500 --resume
if %errorlevel% neq 0 echo 600-s orchestrator exit %errorlevel%
echo === DONE 1e === %date% %time%
