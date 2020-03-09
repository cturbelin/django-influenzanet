# django-influenzanet
Django add-on for influenzanet django website

## Installation

```bash
pip install -e git://github.com/cturbelin/django-influenzanet.git#egg=django-influenzanet
```

In local_settings.py:

Add the variable or add a tupple element in LOCAL_APPS

```python

LOCAL_APPS = (
 'influenzanet',
)


```

Now test with manage.py

Some commands should appear:

 - survey_modify

