Docker setup for lisa project. Also includes python code for syncing 
and initializing the db. This code must be run using WSL python because 
[instructure-dap-client](https://pypi.org/project/instructure-dap-client/)  
requires it.  
Set a cron job like 0 6,18 * * * /path/to/repo/run.sh to sync the db 
every 6am and 6pm automatically. Add a task to Windows Task Scheduler to 
ensure wsl Ubuntu 22.04 starts on machine startup so that the cron job can run.  
^ I'm not entirely sure this will work but we'll find out