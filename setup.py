#!/usr/bin/env python3
"""
OCI Generative AI Agent Setup Script (Python SDK version)
---------------------------------------------------------
Creates:
  - Object Storage bucket
  - Uploads dataset file
  - Knowledge Base
  - Data Source
  - Agent
  - RAG Tool
  - Agent Endpoint

Outputs all OCIDs into GENERATED_OCIDS.txt

Prerequisites:
  - Python 3.9+
  - pip install oci
  - ~/.oci/config configured (DEFAULT profile or set OCI_CLI_PROFILE)
  - Proper IAM policies
"""

import argparse
import oci
from pathlib import Path
from datetime import datetime

OCIDS_FILE = "GENERATED_OCIDS.txt"
#BUCKET_NAME = "ai-workshop-labs-datasets"
FILE_TO_UPLOAD = "TripAdvisorReviewsMultiLangCSV_to_text_small.txt"

def generate_unique_bucket_name(base_name="ai-workshop-labs-datasets"):
    """Generate a unique bucket name using timestamp."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{base_name}-{timestamp}"


def create_bucket(os_client, ns, compartment_id, bucket_name):
    print(f"🔄 Checking if bucket '{bucket_name}' exists...")
    try:
        resp = os_client.get_bucket(ns, bucket_name)
        print(f"✅ Bucket already exists: {resp.data.name}")
        return resp.data.name
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            print(f"🔄 Creating bucket '{bucket_name}'...")
            details = oci.object_storage.models.CreateBucketDetails(
                name=bucket_name,
                compartment_id=compartment_id,
                public_access_type="NoPublicAccess",
                storage_tier="Standard"
            )
            resp = os_client.create_bucket(ns, details)
            print(f"✅ Bucket created: {resp.data.name}")
            return resp.data.name
        raise


def upload_file(os_client, ns, bucket_name, file_path):
    object_name = Path(file_path).name
    print(f"🔄 Uploading file '{object_name}' to bucket '{bucket_name}'...")
    
    try:
        # First try to upload without if_match (for new objects)
        with open(file_path, "rb") as f:
            os_client.put_object(ns, bucket_name, object_name, f)
        print(f"✅ File uploaded successfully: {object_name}")
    except oci.exceptions.ServiceError as e:
        if e.status == 409:  # Conflict - object already exists
            # Try again with if_match for overwrite
            print(f"🔄 Object already exists, overwriting...")
            with open(file_path, "rb") as f:
                os_client.put_object(ns, bucket_name, object_name, f, if_match="*")
            print(f"✅ File overwritten successfully: {object_name}")
        else:
            raise
    
    return object_name


def create_knowledge_base(agent_client, compartment_id):
    print("🔄 Creating knowledge base...")
    details = oci.generative_ai_agent.models.CreateKnowledgeBaseDetails(
        display_name="Hotel_Concierge_Knowledge_Base",
        description="Knowledge base containing hotel guest reviews",
        compartment_id=compartment_id,
        index_config={"indexConfigType": "DEFAULT_INDEX_CONFIG", "shouldEnableHybridSearch": True}
    )
    resp = agent_client.create_knowledge_base(details)
    kb_id = resp.data.id
    print(f"✅ Knowledge base created (ID: {kb_id})")
    return kb_id


def create_data_source(agent_client, compartment_id, kb_id, ns, bucket_name, object_name):
    print("🔄 Creating data source...")
    
    # Create ObjectStoragePrefix object
    prefix = oci.generative_ai_agent.models.ObjectStoragePrefix(
        namespace_name=ns,
        bucket_name=bucket_name,
        prefix=object_name
    )
    
    # Create OciObjectStorageDataSourceConfig object
    data_source_config = oci.generative_ai_agent.models.OciObjectStorageDataSourceConfig(
        object_storage_prefixes=[prefix]
    )
    
    details = oci.generative_ai_agent.models.CreateDataSourceDetails(
        display_name="Hotel Reviews Data Source",
        description="TripAdvisor Reviews dataset",
        compartment_id=compartment_id,
        knowledge_base_id=kb_id,
        data_source_config=data_source_config
    )
    resp = agent_client.create_data_source(details)
    ds_id = resp.data.id
    print(f"✅ Data source created (ID: {ds_id})")
    return ds_id


def create_data_ingestion_job(agent_client, compartment_id, ds_id, kb_id):
    """Create a data ingestion job to process data from the data source into the knowledge base."""
    print("🔄 Creating data ingestion job...")
    
    details = oci.generative_ai_agent.models.CreateDataIngestionJobDetails(
        display_name="Hotel Reviews Data Ingestion",
        description="Data ingestion job for TripAdvisor reviews dataset",
        compartment_id=compartment_id,
        data_source_id=ds_id
    )
    
    resp = agent_client.create_data_ingestion_job(details)
    ingestion_job_id = resp.data.id
    print(f"✅ Data ingestion job created (ID: {ingestion_job_id})")
    print("💡 Data ingestion will run in the background. You can monitor progress in the OCI Console.")
    
    return ingestion_job_id


def create_agent(agent_client, compartment_id, display_name, description, welcome_message):
    print(f"🔄 Creating agent: {display_name}...")
    details = oci.generative_ai_agent.models.CreateAgentDetails(
        display_name=display_name,
        description=description,
        welcome_message=welcome_message,
        compartment_id=compartment_id
    )
    resp = agent_client.create_agent(details)
    agent_id = resp.data.id
    print(f"✅ Agent created: {display_name} (ID: {agent_id})")
    return agent_id


def create_rag_tool(agent_client, compartment_id, agent_id, kb_id):
    print(f"🔄 Creating RAG tool for agent...")
    details = oci.generative_ai_agent.models.CreateToolDetails(
        description="RAG tool for concierge services",
        compartment_id=compartment_id,
        agent_id=agent_id,
        tool_config={
            "toolConfigType": "RAG_TOOL_CONFIG",
            "knowledgeBaseConfigs": [{"knowledgeBaseId": kb_id}]
        }
    )
    resp = agent_client.create_tool(details)
    tool_id = resp.data.id
    print(f"✅ RAG tool created (ID: {tool_id})")
    return tool_id


def create_agent_endpoint(agent_client, compartment_id, agent_id, display_name):
    print(f"🔄 Creating endpoint for {display_name}...")
    details = oci.generative_ai_agent.models.CreateAgentEndpointDetails(
        display_name=f"{display_name}_Endpoint",
        description=f"Endpoint for {display_name}",
        compartment_id=compartment_id,
        agent_id=agent_id
    )
    resp = agent_client.create_agent_endpoint(details)
    endpoint_id = resp.data.id
    print(f"✅ Endpoint created for {display_name} (ID: {endpoint_id})")
    return endpoint_id


def write_ocids(bucket_name, kb_id, ds_id, ingestion_job_id, agent1_id, agent1_endpoint_id, agent1_tool_id, agent2_id, agent2_endpoint_id):
    with open(OCIDS_FILE, "w") as f:
        f.write(f"BUCKET_NAME={bucket_name}\n")
        f.write(f"KNOWLEDGEBASE_ID={kb_id}\n")
        f.write(f"DATASOURCE_ID={ds_id}\n")
        f.write(f"DATA_INGESTION_JOB_ID={ingestion_job_id}\n")
        f.write(f"HOTEL_CONCIERGE_AGENT_ID={agent1_id}\n")
        f.write(f"HOTEL_CONCIERGE_AGENT_ENDPOINT_ID={agent1_endpoint_id}\n")
        f.write(f"HOTEL_CONCIERGE_AGENT_RAG_TOOL_ID={agent1_tool_id}\n")
        f.write(f"HOTEL_CONCIERGE_AGENT_ADK_ID={agent2_id}\n")
        f.write(f"HOTEL_CONCIERGE_AGENT_ADK_ENDPOINT_ID={agent2_endpoint_id}\n")
    print(f"✅ All OCIDs written to {OCIDS_FILE}")


def main():
    print("🚀 Starting OCI Generative AI Agent Setup...")
    print("=" * 60)
    
    parser = argparse.ArgumentParser(description="OCI Generative AI Agent Setup")
    parser.add_argument("--compartment-id", help="Optional compartment OCID (defaults to tenancy from OCI config)")
    args = parser.parse_args()

    # Load config (DEFAULT profile or OCI_CLI_PROFILE if set)
    print("🔄 Loading OCI configuration...")
    config = oci.config.from_file("~/.oci/config", oci.config.DEFAULT_PROFILE)

    # Default: tenancy from config file
    compartment_id = args.compartment_id if args.compartment_id else config["tenancy"]
    print(f"✅ Using compartment ID: {compartment_id}")

    print("🔄 Initializing OCI clients...")
    os_client = oci.object_storage.ObjectStorageClient(config)
    agent_client = oci.generative_ai_agent.GenerativeAiAgentClient(config)
    namespace = os_client.get_namespace().data
    print(f"✅ Object Storage namespace: {namespace}")

    # Generate a unique bucket name
    BUCKET_NAME = generate_unique_bucket_name()

    print("\n📦 STEP 1: Setting up Object Storage")
    print("-" * 40)
    bucket = create_bucket(os_client, namespace, compartment_id, BUCKET_NAME)
    object_name = upload_file(os_client, namespace, bucket, FILE_TO_UPLOAD)

    print("\n🧠 STEP 2: Creating Knowledge Base and Data Source")
    print("-" * 40)
    kb_id = create_knowledge_base(agent_client, compartment_id)
    ds_id = create_data_source(agent_client, compartment_id, kb_id, namespace, bucket, object_name)
    
    print("\n📊 STEP 3: Data Ingestion")
    print("-" * 40)
    ingestion_job_id = create_data_ingestion_job(agent_client, compartment_id, ds_id, kb_id)

    print("\n🤖 STEP 4: Creating Agents")
    print("-" * 40)
    
    # Create first agent (Hotel_Concierge_Agent) with RAG tool
    print("\n🔹 Creating Hotel_Concierge_Agent (with RAG tool)...")
    agent1_id = create_agent(
        agent_client, 
        compartment_id, 
        "Hotel_Concierge_Agent",
        "Hotel Concierge Agent for basic interactions with RAG capabilities",
        "Hello! I'm your Hotel Concierge Agent. I can help you with information from our guest reviews. How can I assist you with your stay today?"
    )
    agent1_tool_id = create_rag_tool(agent_client, compartment_id, agent1_id, kb_id)
    agent1_endpoint_id = create_agent_endpoint(agent_client, compartment_id, agent1_id, "Hotel_Concierge_Agent")

    # Create second agent (Hotel_Concierge_Agent_ADK) without RAG tool
    print("\n🔹 Creating Hotel_Concierge_Agent_ADK (for ADK usage)...")
    agent2_id = create_agent(
        agent_client, 
        compartment_id, 
        "Hotel_Concierge_Agent_ADK",
        "Hotel Concierge Agent for ADK (Agent Development Kit) usage",
        "Hello! I'm your Hotel Concierge Agent for ADK. How can I assist you with your stay today?"
    )
    agent2_endpoint_id = create_agent_endpoint(agent_client, compartment_id, agent2_id, "Hotel_Concierge_Agent_ADK")

    print("\n💾 STEP 5: Saving Configuration")
    print("-" * 40)
    write_ocids(bucket, kb_id, ds_id, ingestion_job_id, agent1_id, agent1_endpoint_id, agent1_tool_id, agent2_id, agent2_endpoint_id)

    print("\n🎉 Setup Complete!")
    print("=" * 60)
    print("✅ Created resources:")
    print(f"   • Bucket: {bucket}")
    print(f"   • Knowledge Base: {kb_id}")
    print(f"   • Data Source: {ds_id}")
    print(f"   • Data Ingestion Job: {ingestion_job_id}")
    print(f"   • Hotel_Concierge_Agent: {agent1_id}")
    print(f"   • Hotel_Concierge_Agent_ADK: {agent2_id}")
    print(f"   • RAG Tool: {agent1_tool_id}")
    print(f"   • Endpoints: {agent1_endpoint_id}, {agent2_endpoint_id}")
    print(f"\n📄 All OCIDs saved to: {OCIDS_FILE}")


if __name__ == "__main__":
    main()
