# Anonymization of users

The package provides an anonymization procedure after a user request.

## Requirements

The package doesn't handles the user request but expect a survey to be filled by a user to request for account unsubscription or deletion.

The survey must have one question named Q1 with following options (only response encoding is shown) :
 - '0' : User wants account unsubscription (personal identifying data will be removed like email, username, ...)
 - '1' : User wants account unsubscription AND data removal

Survey data must be provided by the survey engine of platform (data table will be pollster_results_[survey]) where [survey] is the survey name
used to register request of unsubscription.

## Installation

Once package is installed, anonymization feature need some configuration to be activated

In local_settings.py:

```python
IFN_USE_ANONYMIZE = True
IFN_ANONYMIZE_SURVEY = '[survey]'
```
Replace [survey] by the name of the deactivation survey on you platform ('deactivate' if you use the provided survey xml for example)

Then migrate:

```bash
python manage.py migrate influenzanet
```

### Usage

Command is `ifn_anonymize`

```bash
python manage.py ifn_anonymize
```

Without options the command will run and show actions but will not save them in the db (no data will be removed or changed)

To make the change permanent add '--commit' to the command

Options :

    - '--debug' : will show queries
    - '--commit' : will save the actions
