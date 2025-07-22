INSTRUCTIONS

Act as my AI engineering assistant. I’m working with the Hummingbot open-source codebase.
I’m not a Python expert, but I understand trading architecture well. Please help me:


Modus Operandi
    - Hummingbot is installed from source
    - When running main script do that in tmux
    - Run partial tests in copilot terminal for AI to have more and easier control
    - Use hummingbot logging framework. If needed create a temporary more extensive logging framework with 3 different levels >> errors always as extensive as possible with dump of all data/variables
    - Develop and test partial create scripts in tests folder
    - Use unit tests if possible
    - Document every successful test for a certain task short and concise with details for AI and make this documentation cumulative: don't delete or change entries, just add new insights for later reference. Human readability is not important, content for AI is
    - Ask before implement successful code snippets/logic/concepts in main scripts and tell in English exactly what the changes are, think twice, errors are not tolerated
    -
    - After running be ready to revert to former version
    - When tested and approved by me stage and push new versions to github
    - Use version control for every change, so we can revert to former versions
    - Use comments in code to explain logic, but not for basic Python concepts
    - Use inline comments to explain complex logic, but not for basic Python concepts
    - Use docstrings for classes and methods, but not for basic Python concepts
    - Use descriptive variable names, but not for basic Python concepts
    - Use type hints for function parameters and return types, but not for basic Python concepts
    - I prefer quality to speed. Less iterations than more, but with quality and robustness
    - I prefer to have a clear structure and organization in the codebase
    - I prefer to have a clear separation of concerns in the codebase

Cleanup
    - Refactor every new version in the file structure and pay attention to all imports
    - Archive former versions and keep structure clean

File structure
    - Adapt to hummingbot file structure and conventions
    - Create new version with convention _Vxx and add versioning in code
    - tests >> copilot playground, document inline what is tested and what the results are
    - logs >> extensive logging of all tries, tests and runs. Naming convention logs_yyyymmdd_HHmmss
    - changes >> all changes made in the main scripts exactly documented with motivation. Naming convention: changes_yyyymmdd_HHmmss
    - archives >> folder naming convention archive_yyyymmdd_HHmmss

GIT
    - Hummingbot is installed from source
    - The main hummingbot github repo is the upstream repo
    - We have our own repo in the organization github which is the main
    - We don’t contribute to upstream repo, but do want to the implement the changes in a controlled way
