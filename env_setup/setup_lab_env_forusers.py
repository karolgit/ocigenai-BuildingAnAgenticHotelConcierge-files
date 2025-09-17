import oci
import re

# -------------------------------
# Config and clients
# -------------------------------
config = oci.config.from_file()  # Default: ~/.oci/config
identity_client = oci.identity.IdentityClient(config)

tenancy_id = config["tenancy"]

# -------------------------------
# Validation and sanitization
# -------------------------------
def validate_name(name):
    """Validate OCI resource name (letters, numbers, ., -, _, ;, +)."""
    if not name:
        return False
    if len(name) > 100:
        return False
    if not re.match(r'^[a-zA-Z0-9.\-_;+]+$', name):
        return False
    return True

def get_valid_name(prompt):
    """Prompt user until a valid name is provided."""
    while True:
        name = input(prompt).strip()
        if validate_name(name):
            return name
        print("Invalid name! Use only a-z, A-Z, 0-9, . - _ ; + Max 100 chars, no spaces.")

def sanitize_compartment_name(email):
    """Convert email to OCI-compatible compartment name and append 'Compartment'."""
    name = email.split("@")[0].replace("+", "_")
    name = re.sub(r'[^a-zA-Z0-9.\-_;]', '', name)
    return f"{name}Compartment"

def sanitize_username(email):
    """Keep full email as OCI username (with + and @)."""
    name = re.sub(r'[^a-zA-Z0-9.\-_;+@]', '', email)
    return name

# -------------------------------
# Input
# -------------------------------
lab_group_name = get_valid_name("Enter Lab Group Name (alphanumeric, .-_ ; + only): ")
users_file = "users.txt"  # TXT file with one email per line

# -------------------------------
# Group functions
# -------------------------------
def get_or_create_group(group_name):
    groups = identity_client.list_groups(compartment_id=config["tenancy"]).data
    existing_group = next((g for g in groups if g.name == group_name), None)
    if existing_group:
        print(f"Group '{group_name}' already exists. Using existing group.")
        return existing_group.id
    
    request = oci.identity.models.CreateGroupDetails(
        compartment_id=config["tenancy"],
        name=group_name,
        description=f"Lab group {group_name}"
    )
    group = identity_client.create_group(request).data
    print(f"Created group: {group.name}, OCID: {group.id}")
    return group.id

group_id = get_or_create_group(lab_group_name)

# -------------------------------
# Read users from file
# -------------------------------
def read_users(file_path):
    with open(file_path, "r") as f:
        users = [line.strip() for line in f if line.strip()]
    valid_users = []
    for user in users:
        sanitized = sanitize_username(user)
        if validate_name(sanitized.replace("@", "")):
            valid_users.append(sanitized)
        else:
            print(f"Skipping invalid username: {user}")
    return valid_users

users = read_users(users_file)

# -------------------------------
# Compartment functions
# -------------------------------
def get_or_create_compartment(name):
    compartments = identity_client.list_compartments(
        compartment_id=config["tenancy"],
        compartment_id_in_subtree=True,
        lifecycle_state=oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
    ).data
    existing = next((c for c in compartments if c.name == name), None)
    if existing:
        print(f"Compartment '{name}' already exists. Using existing compartment.")
        return existing.id
    
    request = oci.identity.models.CreateCompartmentDetails(
        compartment_id=config["tenancy"],
        name=name,
        description=f"Compartment for {name}"
    )
    compartment = identity_client.create_compartment(request).data
    print(f"Created compartment: {compartment.name}, OCID: {compartment.id}")
    return compartment.id

user_compartments = {}
for user in users:
    comp_name = sanitize_compartment_name(user)
    user_compartments[user] = get_or_create_compartment(comp_name)

# -------------------------------
# User functions
# -------------------------------
def get_or_create_user(email):
    """Create the user if it does not exist."""
    users_list = identity_client.list_users(compartment_id=config["tenancy"]).data
    user_obj = next((u for u in users_list if u.name == email), None)
    if user_obj:
        print(f"User '{email}' already exists. Using existing user.")
        return user_obj.id

    request = oci.identity.models.CreateUserDetails(
        compartment_id=config["tenancy"],
        name=email,
        description=f"Lab user {email}",
        email=email  # primary email MUST be set
    )
    user_obj = identity_client.create_user(request).data
    print(f"Created user: {email}, OCID: {user_obj.id}")
    return user_obj.id

def add_user_to_group(user_id, group_id, tenancy_id):
    """
    Safely add a user to a group.
    Skips if the user is already a member of the group.
    """
    try:
        # Must provide tenancy_id as compartment_id
        memberships = oci.pagination.list_call_get_all_results(
            identity_client.list_user_group_memberships,
            tenancy_id,
            user_id=user_id
        ).data

        for membership in memberships:
            if membership.group_id == group_id:
                print(f"User {user_id} is already in group {group_id}, skipping.")
                return

        # If not already in the group, add them
        details = oci.identity.models.AddUserToGroupDetails(
            user_id=user_id,
            group_id=group_id
        )
        identity_client.add_user_to_group(details)
        print(f"✅ Added user {user_id} to group {group_id}")

    except oci.exceptions.ServiceError as e:
        if e.status == 409:
            print(f"⚠️ User {user_id} is already in group {group_id} (duplicate). Skipping.")
        else:
            raise



# -------------------------------
# Policy functions
# -------------------------------
def create_policy(policy_name, statements, compartment_id=config["tenancy"]):
    if not validate_name(policy_name):
        print(f"Skipping invalid policy name: {policy_name}")
        return None
    policies = identity_client.list_policies(compartment_id=compartment_id).data
    if any(p.name == policy_name for p in policies):
        print(f"Policy '{policy_name}' already exists. Skipping.")
        return None
    policy_details = oci.identity.models.CreatePolicyDetails(
        compartment_id=compartment_id,
        name=policy_name,
        description=f"Policy for {policy_name}",
        statements=statements
    )
    policy = identity_client.create_policy(policy_details).data
    print(f"Created policy: {policy.name}, OCID: {policy.id}")
    return policy.id

# -------------------------------
# Create base policy (same as group)
# -------------------------------
# Base policies applicable to tenancy
base_statements = [
    f"allow group '{lab_group_name}' to use cloud-shell in tenancy",
    f"allow group '{lab_group_name}' to use cloud-shell-public-network in tenancy",
    f"allow group '{lab_group_name}' to manage object-family in tenancy",
    f"allow group '{lab_group_name}' to manage buckets in tenancy",
    f"allow group '{lab_group_name}' to manage objects in tenancy",
    f"allow group '{lab_group_name}' to use generative-ai-family in tenancy",
    f"allow group '{lab_group_name}' to manage adm-knowledge-bases in tenancy",
    f"allow group '{lab_group_name}' to manage genai-agent-family in tenancy"
]

# Add all per-user compartments to the same policy
for user in users:
    comp_name = sanitize_compartment_name(user)
    base_statements.append(f"allow group '{lab_group_name}' to manage all-resources in compartment {comp_name}")

# Create a single policy for the group
create_policy(f"{lab_group_name}-BasePolicy", base_statements)

# -------------------------------
# Create users and add to group
# -------------------------------
for user_email in users:
    user_id = get_or_create_user(user_email)
    add_user_to_group(user_id, group_id,tenancy_id)

print("Lab group setup completed successfully!")
