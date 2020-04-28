# Installation

## Install package

In the influenzanet website directory

```bash
. bin/activate
pip install -e git+git://github.com/cturbelin/django-influenzanet.git#egg=django-influenzanet
```

The package should be installed

Check in : lib/python2.7/site-packages, there should be a "influenzanet" directory

If it's not, go in src/django-influenzanet
and run

```bash
cd src/django-influenzanet
pip install .
```

And check again.

## Register it to app

In local_settings.py add (add variable or add a line into it if already there)

```python
LOCAL_APPS = (
 'influenzanet',
)

```

## Update the package

To update it from git, in the influenzanet installation dir (where the website lives)

```bash
source bin/activate
cd src/django-influenzanet
git pull
pip install .
```
