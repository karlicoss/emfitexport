# see https://github.com/karlicoss/pymplate for up-to-date reference


from setuptools import setup, find_packages # type: ignore


def main():
    pkg = 'emfitexport'
    setup(
        name=pkg,
        zip_safe=False,
        packages=[pkg],
        package_dir={'': 'src'},
        package_data={pkg: ['py.typed']},

        url='',
        author='',
        author_email='',
        description='',
    )


if __name__ == '__main__':
    main()

# TODO
# from setuptools_scm import get_version
# https://github.com/pypa/setuptools_scm#default-versioning-scheme
# get_version(version_scheme='python-simplified-semver', local_scheme='no-local-version')
