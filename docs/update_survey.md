# Update a survey


## Test (will juste raise an error for missing file)
python manage.py survey_modify


## Get modification json file
wget https://www.grippenet.fr/media/results/coronavirus.json

## How it works
 - the command will modify the survey definition
 - It will generate a file .sql to apply to the database to make the modification to the current data table

## Backup the survey definition +++ (using the django admin survey editor or the following command)
python manage.py survey_export

## Test application with the survey_modify command

Parameters :
 * '--locale=[country]'  locale to use to create the country list
 * '--survey=name'  	  name of the survey to apply to
 * '--commit'  		     will apply the changes (without it it will only apply changes but cancel them)
 * '--translation' will build the xml translation file and output it (as [survey].i18n.xml file)

```bash
python manage.py survey_modify --file=coronavirus.json --survey=weekly --locale=xx 
```

# If everything seems ok relaunch the command by adding --commit
## Apply the SQL modifications 
psql -d [database] < weekly.sql