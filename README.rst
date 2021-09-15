
Galaxy Tool Database
---------------------

Small package for managaging a YAML database of Galaxy tool runtime metadata.

This Python project can be installed from PyPI using ``pip``.

::

    $ python3 -m venv .venv
    $ . .venv/bin/activate
    $ pip install gx-tool-db

This will install the executable `gx-tool-db`.

::

    $ gx-tool-db --help

This library and associated scripts are licensed under the MIT License.

-------------
Development
-------------

Run `gx-tool-db` from a clone of the repository and with local changes applied using `pip install -e`.

::

    $ python3 -m venv .venv
    $ . .venv/bin/activate
    $ pip install -e .

----------------
Getting Started
----------------

Start by bootstrapping data from a few servers:

::

    $ mkdir my_tool_db
    $ cd my_tool_db
    $ gx-tool-db import-server --server org
    $ gx-tool-db import-server --server eu
    $ gx-tool-db import-server --server test

Next we can use the bootstrapped data to dump information about the latest
version of all tools across all servers or at individual servers. This data
can be exported as standard CSV files or more typical Galaxy style tabular
("tsv") data.

::

    $ gx-tool-db export-tabular --all-coverage --output coverage_public_servers.tsv
    $ gx-tool-db export-tabular --coverage org --coverage test --output coverage_public_servers.csv

Next lets start apply tool labels. Lets read a list of deprecated tool IDs from a file or URL using
the ``import-label`` command.

::

    $ gx-tool-db import-label https://gist.githubusercontent.com/jmchilton/651dad1289cb897cfaa92a86a39a184e/raw/65da6b11353732b550f9b1e0f9dc218a6bcef916/gistfile1.txt deprecated

One can also apply a label to all tool IDs from a workflow or a directory of workflows using the
``label-workflow-tools`` command.

::

    $ git clone https://github.com/galaxyproject/iwc.git
    $ gx-tool-db label-workflow-tools iwc/ iwc_required

The deprecated and iwc_required labels can now be used to build toolbox-related artifacts.
The following command will create two Ephemeris/ansible-galaxy-tools install YAML files
from main's (usegalaxy.org) toolset. The first will include only tools required by IWC workflows and the
second will contain main's whole toolbox with the exclusion of deprecated tools.

::

    $ gx-tool-db export-install-yaml main --require_label iwc_required
    $ gx-tool-db export-install-yaml main --exclude_label deprecated

Tool panel views (https://docs.google.com/presentation/d/1qKhWhJYe3LmDd0sKaY247s4DxjjZdi807YV_4TqYfGA)
can also be constructed from these tool labels.

The following command will produce a file (best_practices.yml) that will be a frozen version of usegalaxy.org
tool panel containing only tools with the label ``iwc_required``.

::

    $ gx-tool-db export-panel-view best_practices main --require_label iwc_required

The following command will produce a file (best_practices.yml) that will be a frozen version of usegalaxy.org
tool panel containing only tools with the label ``iwc_required``.

Since Galaxy doesn't know about these external labels, the panel is frozen and the above command
needs to be re-run as new tools are labelled. Alternatively, when using ``--exclude_label``
main's sections can have tools added to them and they will be assumed to be non-deprecated and
will appear in the tool panel.

::

    $ gx-tool-db export-panel-view best_practices main --exclude_label deprecated

This application provides some utilities for automatically applying these tool labels
but manual curation is still important when grouping tools. This can be done in the YAML
directly or using spreadsheet software.

Use ``--label`` with the ``export-tabular`` command shown above to include columns
for specified labels (these labels don't even need to exist ahead of time).
The same spreadsheet can then be re-imported using the ``import-tabular`` and the
same labels to read the data back into the structured gx-tool-db database file.

::

    $ gx-tool-db export-tabular --all-coverage --label really_cool --label meh --output to_curate.tsv
    $ gx-tool-db import-tabular to_curate.tsv --label really_cool --label meh

For these spreadsheet commands, the target spreadsheet can also be an Google Sheets
ID for collobrative editing.

::

    $ gx-tool-db export-tabular --all-coverage --label really_cool --label meh --output 'sheet:1N84CziEyW0Z109slrL33cuFt3Wpuu037zogkBMhk-C0'
    $ gx-tool-db import-tabular 'sheet:1N84CziEyW0Z109slrL33cuFt3Wpuu037zogkBMhk-C0' --label really_cool --label meh

Finally, to assist in maual curation of the database tool runtime results can be
stored in the database as well.

::

    $ gx-tool-db import-tests https://raw.githubusercontent.com/almahmoud/anvil-misc/master/reports/anvil-production/tool-tests/gxy-auto-06-27-16-32-39-1/results.json anvil

Test data summaries can then be included as part `export-tabular`` to help curate tool labels -
either all test data labels or specified ones.

::

    $ gx-tool-db export-tabular --all-tests --label really_cool --label meh --output to_curate_all_the_tests.tsv
    $ gx-tool-db export-tabular --tests anvil --label really_cool --label meh --output to_curate_only_anvil_tests.tsv

Metadata about how tools are used within `Galaxy Training Network`_ tutorials can be loaded as well.

    $ git clone https://github.com/galaxyproject/training-material.git
    $ gx-tool-db import-trainings training-material

Columns for these tutorials and topics referencing tools can be then included with ``export-tabular`` with the
``--training-topcis`` and ``--training-tutorials`` flags respectively.

.. _Galaxy: https://galaxyproject.org/
.. _Galaxy Training Network: https://training.galaxyproject.org/
