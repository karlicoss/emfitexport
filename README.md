

Export your personal [Emfit QS](https://www.emfit.com/active-life-sleep-and-recovery) sleep data.

# Setting up

1.  Clone the repository: `git clone https://github.com/karlicoss/emfitexport`
2.  From the cloned repository, run `pip3 install --user --editable .`.
3.  Note that unfortunately, the script needs your Emfit username and password, because the token expires after a few weeks.

<!--
3. Log in to your [Emfit dashboard](https://qs.emfit.com) and extract the `Authorisation` header using browser's devtools.
   It should look like `Bearer SOME_LONG_STRING`.
   If you don't know how to do it, [here](https://willschenk.com/articles/2019/reverse_engineering_apis_using_chrome) is a nice tutorial.
-->

<!-- TODO really need a way to install dependencies only... or maybe it's fair that setup.py reads requirements.txt, dunno -->

# Exporting

Usage:

**Recommended**: create `secrets.py` keeping your API parameters, e.g.:

    username = "USERNAME"
    password = "PASSWORD"

After that, use:

    python3 -m emfitexport.export --secrets /path/to/secrets.py

That way you type less and have control over where you keep your plaintext secrets.

**Alternatively**, you can pass parameters directly, e.g.

    python3 -m emfitexport.export --username <username> --password <password>

However, this is verbose and prone to leaking your keys/tokens/passwords in shell history.

I **highly** recommend checking exported files at least once just to make sure they contain everything you expect from your export.
If they don’t, please feel free to ask or raise an issue!

# Updating README

This README is generated from a ‘literate’ Quarto [README.qmd](README.qmd) via the following command:

`tox -e quarto`

If you want to correct something, feel free to simply update `README.md` though, I can reconcile the changes next time I regenerate it.
