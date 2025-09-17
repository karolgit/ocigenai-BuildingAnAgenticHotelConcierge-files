import oci
from oci.oda import OdaClient
from oci.ai_service_language import AIServiceLanguageClient

# -------------------------------
# Config and clients
# -------------------------------
config = oci.config.from_file()
identity_client = oci.identity.IdentityClient(config)

# Digital Assistant client (Agents / KnowledgeBases)
oda_client = OdaClient(config)

# Generative AI client (Tools / Endpoints)
ai_client = AIServiceLanguageClient(config)

# -------------------------------
# Resource cleanup functions
# -------------------------------
def delete_agents(compartment_id):
    try:
        agents = oda_client.list_odas(compartment_id=compartment_id).data
        for agent in agents:
            print(f"Deleting Agent {agent.display_name}")
            oda_client.delete_oda(agent.id)
    except oci.exceptions.ServiceError as e:
        print(f"No Agents or error: {e}")

def delete_knowledgebases(compartment_id):
    try:
        kbs = oda_client.list_knowledge_bases(compartment_id=compartment_id).data
        for kb in kbs:
            print(f"Deleting KnowledgeBase {kb.display_name}")
            oda_client.delete_knowledge_base(kb.id)
    except oci.exceptions.ServiceError as e:
        print(f"No KnowledgeBases or error: {e}")

def delete_tools(compartment_id):
    try:
        tools = ai_client.list_tools(compartment_id=compartment_id).data
        for tool in tools:
            print(f"Deleting Tool {tool.display_name}")
            ai_client.delete_tool(tool.id)
    except oci.exceptions.ServiceError as e:
        print(f"No Tools or error: {e}")

def delete_endpoints(compartment_id):
    try:
        endpoints = ai_client.list_endpoints(compartment_id=compartment_id).data
        for ep in endpoints:
            print(f"Deleting Endpoint {ep.display_name}")
            ai_client.delete_endpoint(ep.id)
    except oci.exceptions.ServiceError as e:
        print(f"No Endpoints or error: {e}")

# -------------------------------
# Delete compartments and resources
# -------------------------------
def delete_lab_compartments(lab_group_name):
    compartments = identity_client.list_compartments(
        compartment_id=config["tenancy"],
        compartment_id_in_subtree=True,
        lifecycle_state=oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
    ).data

    # Filter compartments by lab group name
    lab_compartments = [c for c in compartments if lab_group_name.lower() in c.name.lower()]

    for comp in lab_compartments:
        print(f"\nCleaning resources in compartment {comp.name} (OCID: {comp.id})...")

        # Delete resources
        delete_agents(comp.id)
        delete_knowledgebases(comp.id)
        delete_tools(comp.id)
        delete_endpoints(comp.id)

        # Delete the compartment itself
        try:
            identity_client.delete_compartment(comp.id)
            print(f"Deleted compartment {comp.name}")
        except oci.exceptions.ServiceError as e:
            print(f"Error deleting compartment {comp.name}: {e}")

# -------------------------------
# Main
# -------------------------------
lab_group_name = input("Enter Lab Group Name to delete resources from: ").strip()
delete_lab_compartments(lab_group_name)
