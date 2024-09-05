# Ansible Call
[![CI](https://github.com/cheburakshu/ansible-call/actions/workflows/cicd.yml/badge.svg)](https://github.com/cheburakshu/ansible-call/actions/workflows/cicd.yml)

`ansible-call` is a Python package that allows you to interact with Ansible modules directly from your Python code. This package is designed to make it easier to call and work with Ansible modules programmatically.

## Installation

You can install `ansible-call` from PyPI using pip:

```bash
pip install ansiblecall
```

## Example

```python
import ansiblecall

# Call the 'ping' module from 'ansible.builtin'
result = ansiblecall.module('ansible.builtin.ping', data='hello')

# Print the result
print(result)

# Prints
# {'ping': 'hello'}
```

## Contributing

Contributions are welcome! If you'd like to contribute to ansible-call, please fork the repository and submit a pull request with your changes. Make sure to follow the project's coding standards and include tests for any new features.

## License
`ansible-call` is licensed under the GNU GPLv3 License. See the LICENSE file for more details.