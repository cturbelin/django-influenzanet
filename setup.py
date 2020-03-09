#!/usr/bin/env python

from setuptools import setup, find_packages

email ="clement.turbelin@sorbonne-universite.fr"

setup(
    name="django-influenzanet",
    description="Add-on tools for django influenzanet website",
    long_description="\n".join(
        [
            open("README.rst").read(),
        #    open("CHANGES.rst").read(),
        ]
    ),
    keywords="influenzanet",
    author=", ".join(
        [
            "Clément Turbelin",
        ]
    ),
    author_email=email,
    maintainer="Clément Turbelin",
    maintainer_email=email,
    url="https://github.com/cturbelin/django-influenzanet",
    project_urls={
        "Documentation": "https://github.com/cturbelin/django-influenzanet",
        "Source": "https://github.com/cturbelin/django-influenzanet",
        "Tracker": "https://github.com/cturbelin/django-influenzanet/issues",
    },
    license="GPL",
    package_dir={"influenzanet": "influenzanet"},
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    python_requires="=>2.7",
    install_requires=[],
    include_package_data=True,
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Environment :: Plugins",
        "Framework :: Django",
        "Framework :: Django :: 1.3",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Topic :: Influenzanet",
    ],
    zip_safe=False,
)