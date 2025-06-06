"""Shared mock data for tests."""

# Common Proxmox API responses
PROXMOX_VERSION_RESPONSE = {
    'version': '7.4',
    'release': '1',
    'repoid': 'abcd1234'
}

PROXMOX_CLUSTER_STATUS_RESPONSE = [
    {'type': 'cluster', 'name': 'test-cluster', 'quorate': 1, 'nodes': 3},
    {'type': 'node', 'name': 'node1', 'online': 1, 'local': 1, 'nodeid': 1},
    {'type': 'node', 'name': 'node2', 'online': 1, 'local': 0, 'nodeid': 2},
    {'type': 'node', 'name': 'node3', 'online': 1, 'local': 0, 'nodeid': 3}
]

PROXMOX_DNS_RESPONSE = {
    'search': 'example.com',
    'dns1': '8.8.8.8',
    'dns2': '8.8.4.4',
    'dns3': '1.1.1.1'
}

# VM-related mock data
SAMPLE_VM_CONFIG = {
    'vmid': 100,
    'name': 'test-vm',
    'ostype': 'l26',
    'memory': 2048,
    'sockets': 1,
    'cores': 2,
    'agent': 'enabled=1',
    'boot': 'order=scsi0',
    'scsi0': 'local-lvm:vm-100-disk-0,size=32G'
}

SAMPLE_VM_STATUS = {
    'vmid': 100,
    'name': 'test-vm',
    'status': 'running',
    'uptime': 3600,
    'pid': 12345,
    'maxmem': 2147483648,
    'maxdisk': 34359738368,
    'cpu': 0.01,
    'mem': 1073741824,
    'disk': 2147483648,
    'netin': 1024,
    'netout': 2048
}

SAMPLE_K3S_VMS = [
    {
        'vmid': 100, 'name': 'k3s-server-1', 'status': 'running',
        'node': 'node1', 'tags': 'k3s-server', 'maxmem': 4294967296,
        'maxdisk': 68719476736, 'cpu': 0.02, 'uptime': 86400
    },
    {
        'vmid': 101, 'name': 'k3s-agent-1', 'status': 'running',
        'node': 'node2', 'tags': 'k3s-agent', 'maxmem': 2147483648,
        'maxdisk': 34359738368, 'cpu': 0.01, 'uptime': 7200
    },
    {
        'vmid': 102, 'name': 'k3s-storage-1', 'status': 'running',
        'node': 'node3', 'tags': 'k3s-storage', 'maxmem': 2147483648,
        'maxdisk': 107374182400, 'cpu': 0.005, 'uptime': 3600
    }
]

# Configuration templates
BASIC_PROXMOX_CONFIG = {
    'host': 'pve.example.com',
    'user': 'root@pam',
    'password': 'testpass',
    'verify_ssl': True,
    'timeout': 10
}

PROXMOX_CONFIG_WITH_TOKENS = {
    'host': 'pve.example.com',
    'user': 'testuser@pam',
    'api_token_id': 'testuser@pam!mytoken',
    'api_token_secret': 'secret-token-value',
    'verify_ssl': True,
    'timeout': 10
}

FULL_CONFIG_WITH_NODES = {
    'proxmox': BASIC_PROXMOX_CONFIG,
    'nodes': [
        {'vmid': 100, 'role': 'server', 'name': 'k3s-server-1'},
        {'vmid': 101, 'role': 'agent', 'name': 'k3s-agent-1'},
        {'vmid': 102, 'role': 'agent', 'name': 'k3s-agent-2'}
    ]
}

# QGA (Guest Agent) responses
QGA_ENABLED_RESPONSE = {
    'enabled': True,
    'running': True,
    'version': '5.2.0'
}

QGA_DISABLED_RESPONSE = {
    'enabled': False,
    'running': False,
    'version': 'N/A'
}

# Error responses for testing
PROXMOX_AUTH_ERROR = {
    'status_code': 401,
    'reason': 'Unauthorized',
    'content': 'authentication failure'
}

PROXMOX_NOT_FOUND_ERROR = {
    'status_code': 404,
    'reason': 'Not Found',
    'content': 'resource not found'
}

PROXMOX_SERVER_ERROR = {
    'status_code': 500,
    'reason': 'Internal Server Error',
    'content': 'internal server error'
}