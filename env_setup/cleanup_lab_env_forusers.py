import oci
import time
from oci.retry import RetryStrategyBuilder
# -------------------------------
# Config and client
# -------------------------------
config = oci.config.from_file()
identity_client = oci.identity.IdentityClient(config)
# Simple retry strategy (5 max attempts)
retry_strategy = RetryStrategyBuilder().add_max_attempts(5).get_retry_strategy()

# Identity client with retry
identity_client = oci.identity.IdentityClient(config, retry_strategy=retry_strategy)
# -------------------------------
# Helper functions
# -------------------------------
def get_group_by_name(group_name):
    groups = identity_client.list_groups(compartment_id=config["tenancy"]).data
    return next((g for g in groups if g.name == group_name), None)

def list_user_group_memberships(group_id):
    return identity_client.list_user_group_memberships(compartment_id=config["tenancy"], group_id=group_id).data

def remove_user_from_group(user_id, group_id):
    memberships = list_user_group_memberships(group_id)
    membership = next((m for m in memberships if m.user_id == user_id), None)
    if membership:
        identity_client.remove_user_from_group(user_group_membership_id=membership.id)
        print(f"Removed user {user_id} from group {group_id}")

def delete_user(user_id, user_name):
    identity_client.delete_user(user_id)
    print(f"Deleted user {user_name}")

def delete_compartment(compartment_name):
    compartments = identity_client.list_compartments(
        compartment_id=config["tenancy"],
        compartment_id_in_subtree=True,
        lifecycle_state=oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
    ).data
    comp = next((c for c in compartments if c.name == compartment_name), None)
    if comp:
        identity_client.delete_compartment(comp.id)
        print(f"Deleted compartment {compartment_name}")

def delete_policy(policy_name):
    policies = identity_client.list_policies(compartment_id=config["tenancy"]).data
    policy = next((p for p in policies if p.name == policy_name), None)
    if policy:
        identity_client.delete_policy(policy.id)
        print(f"Deleted policy {policy_name}")

def delete_lab_compartments(lab_name):
    compartments = identity_client.list_compartments(
        compartment_id=config["tenancy"],
        compartment_id_in_subtree=True,
        lifecycle_state=oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
    ).data

    for comp in compartments:
        if lab_name in comp.name:
            try:
                identity_client.delete_compartment(comp.id)
                print(f"Deleted compartment {comp.name}")
            except oci.exceptions.ServiceError as e:
                print(f"Failed to delete compartment {comp.name}: {e}")

# -------------------------------
# Main cleanup
# -------------------------------
lab_group_name = input("Enter Lab Group Name to delete: ").strip()
group = get_group_by_name(lab_group_name)

if not group:
    print(f"No group found with name {lab_group_name}")
    # Delete the group itself
    lab_name = lab_group_name
    #lab_name = input("Enter Lab Name to delete: ").strip()
    delete_lab_compartments(lab_name)
    exit(0)

print(f"Found group: {group.name}, OCID: {group.id}")

# Remove users from group and delete users
memberships = list_user_group_memberships(group.id)

users_info = []

for membership in memberships:
    try:
        user = identity_client.get_user(membership.user_id).data
        users_info.append({"id": user.id, "name": user.name})
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            print(f"User {membership.user_id} not found, skipping...")
        else:
            raise

# Delete per-user compartments
# Assumes compartments are named like "<username>Compartment"
# for membership in memberships:
#     user_name = identity_client.get_user(membership.user_id).data.name
#     comp_name = user_name.split("@")[0].replace("+", "_") + "Compartment"
#     delete_compartment(comp_name)


for membership in memberships:
    user_name = identity_client.get_user(membership.user_id).data.name
    comp_name = user_name.split("@")[0].replace("+", "_") + "Compartment"
    try:
        delete_compartment(comp_name)
        time.sleep(1)  # wait 1 second to avoid throttling
    except oci.exceptions.ServiceError as e:
        print(f"Error deleting compartment {comp_name}: {e}")

# Delete policies
base_policy_name = f"{lab_group_name}-BasePolicy"
delete_policy(base_policy_name)

# Delete per-user policies (assumes same naming as creation)
for membership in memberships:
    user_name = identity_client.get_user(membership.user_id).data.name
    comp_name = user_name.split("@")[0].replace("+", "_") + "Compartment"
    policy_name = f"{lab_group_name}-{comp_name}-Policy"
    delete_policy(policy_name)

# Delete the group itself
identity_client.delete_group(group.id)
print(f"Deleted group {lab_group_name}")



