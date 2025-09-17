import oci
import time
from oci.retry import RetryStrategyBuilder
from oci.oda import OdaManagementClient
# -------------------------------
# Config and client
# -------------------------------
config = oci.config.from_file()
identity_client = oci.identity.IdentityClient(config)
# # ODA client for Agents, Knowledge Bases, Tools, Agent Endpoints
# oda_client = oci.oda.OdaClient(config)

# ODA management client for Agents, Knowledge Bases, Tools
oda_client = OdaManagementClient(config)

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

# def delete_lab_compartments(lab_name):
#     compartments = identity_client.list_compartments(
#         compartment_id=config["tenancy"],
#         compartment_id_in_subtree=True,
#         lifecycle_state=oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
#     ).data

#     for comp in compartments:
#         if lab_name in comp.name:
#             try:
#                 identity_client.delete_compartment(comp.id)
#                 print(f"Deleted compartment {comp.name}")
#             except oci.exceptions.ServiceError as e:
#                 print(f"Failed to delete compartment {comp.name}: {e}")

# -------------------------------
# Helper function to wait for deletion
# -------------------------------
def wait_for_deletion(get_func, resource_id, resource_name, resource_type, sleep_sec=5):
    while True:
        try:
            get_func(resource_id)
            print(f"Waiting for {resource_type} '{resource_name}' to be deleted...")
            time.sleep(sleep_sec)
        except oci.exceptions.ServiceError as e:
            if e.status == 404:
                print(f"{resource_type} '{resource_name}' deleted.")
                break
            else:
                raise

# -------------------------------
# Delete functions
# -------------------------------
def delete_tools(compartment_id):
    tools = oda_client.list_tools(compartment_id=compartment_id).data
    for tool in tools:
        print(f"Deleting Tool: {tool.display_name}")
        oda_client.delete_tool(tool.id)
        wait_for_deletion(oda_client.get_tool, tool.id, tool.display_name, "Tool")
        time.sleep(1)

def delete_knowledge_bases(compartment_id):
    kbs = oda_client.list_knowledge_bases(compartment_id=compartment_id).data
    for kb in kbs:
        print(f"Deleting Knowledge Base: {kb.display_name}")
        oda_client.delete_knowledge_base(kb.id)
        wait_for_deletion(oda_client.get_knowledge_base, kb.id, kb.display_name, "Knowledge Base")
        time.sleep(1)

def delete_agents(compartment_id):
    agents = oda_client.list_odas(compartment_id=compartment_id).data
    for agent in agents:
        print(f"Deleting Agent: {agent.display_name}")
        # Delete related Tools and Knowledge Bases first
        delete_tools(compartment_id)
        delete_knowledge_bases(compartment_id)
        # Delete the agent itself
        oda_client.delete_oda(agent.id)
        wait_for_deletion(oda_client.get_oda, agent.id, agent.display_name, "Agent")
        time.sleep(1)

# -------------------------------
# Delete all compartments for a lab group
# -------------------------------
def delete_lab_compartments(lab_group_name):
    # List all active compartments
    compartments = identity_client.list_compartments(
        compartment_id=config["tenancy"],
        compartment_id_in_subtree=True,
        lifecycle_state=oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
    ).data

    # Filter compartments matching the lab group name
    lab_comps = [c for c in compartments if lab_group_name in c.name]

    if not lab_comps:
        print(f"No compartments found for lab group '{lab_group_name}'")
        return

    for comp in lab_comps:
        print(f"\nProcessing compartment '{comp.name}' (OCID: {comp.id})")

        # Delete resources in correct order
        delete_tools(comp.id)
        delete_knowledge_bases(comp.id)
        delete_agents(comp.id)

        # Finally, delete the compartment
        print(f"Deleting compartment: {comp.name}")
        identity_client.delete_compartment(comp.id)
        wait_for_deletion(identity_client.get_compartment, comp.id, comp.name, "Compartment")
        print(f"Compartment '{comp.name}' deleted successfully.\n")

# -------------------------------
# Main cleanup
# -------------------------------
lab_group_name = input("Enter Lab Group Name to delete: ").strip()
group = get_group_by_name(lab_group_name)

if not group:
    print(f"No group found with name {lab_group_name}")
    delete_lab_compartments(lab_group_name)    
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



