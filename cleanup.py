#!/usr/bin/env python3
"""
OCI Generative AI Agent Cleanup Script (Python SDK version)
-----------------------------------------------------------
Deletes all resources created by setup.py in the proper order:
1. For each agent: delete tools, delete endpoints, delete agent
2. Delete knowledge base
3. Delete bucket

Prerequisites:
  - Python 3.9+
  - pip install oci
  - ~/.oci/config configured (DEFAULT profile or set OCI_CLI_PROFILE)
  - GENERATED_OCIDS.txt file from setup.py
"""

import argparse
import oci
import os
from pathlib import Path

OCIDS_FILE = "GENERATED_OCIDS.txt"


def load_ocids():
    """Load OCIDs from the generated file."""
    if not os.path.exists(OCIDS_FILE):
        print(f"❌ Error: {OCIDS_FILE} not found")
        print("Make sure you're running this script from the directory where setup.py was executed.")
        exit(1)
    
    ocids = {}
    with open(OCIDS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                ocids[key] = value
    
    print(f"✅ Loaded OCIDs from {OCIDS_FILE}")
    return ocids


def delete_agent_tools(agent_client, agent_id, agent_name, compartment_id):
    """Delete all tools for a specific agent."""
    print(f"🔄 Listing tools for {agent_name}...")
    
    try:
        # List tools for the agent
        tools_response = agent_client.list_tools(compartment_id=compartment_id, agent_id=agent_id)
        tools = tools_response.data.items
        
        if not tools:
            print(f"✅ No tools found for {agent_name}")
            return
        
        print(f"📋 Found {len(tools)} tool(s) for {agent_name}")
        
        for tool in tools:
            tool_id = tool.id
            tool_name = tool.description or tool.id
            print(f"🔄 Deleting tool: {tool_name}...")
            
            try:
                agent_client.delete_tool(tool_id)
                print(f"✅ Tool deleted: {tool_name}")
            except oci.exceptions.ServiceError as e:
                if e.status == 404:
                    print(f"⚠️  Tool already deleted: {tool_name}")
                else:
                    print(f"❌ Failed to delete tool {tool_name}: {e.message}")
    
    except oci.exceptions.ServiceError as e:
        print(f"❌ Failed to list tools for {agent_name}: {e.message}")


def delete_agent_endpoints(agent_client, agent_id, agent_name, compartment_id):
    """Delete all endpoints for a specific agent."""
    print(f"🔄 Listing endpoints for {agent_name}...")
    
    try:
        # List endpoints for the agent
        endpoints_response = agent_client.list_agent_endpoints(compartment_id=compartment_id, agent_id=agent_id)
        endpoints = endpoints_response.data.items
        
        if not endpoints:
            print(f"✅ No endpoints found for {agent_name}")
            return
        
        print(f"📋 Found {len(endpoints)} endpoint(s) for {agent_name}")
        
        for endpoint in endpoints:
            endpoint_id = endpoint.id
            endpoint_name = endpoint.display_name or endpoint.id
            print(f"🔄 Deleting endpoint: {endpoint_name}...")
            
            try:
                agent_client.delete_agent_endpoint(endpoint_id)
                print(f"✅ Endpoint deleted: {endpoint_name}")
                # Wait a moment for the endpoint to be fully deleted
                import time
                time.sleep(2)
            except oci.exceptions.ServiceError as e:
                if e.status == 404:
                    print(f"⚠️  Endpoint already deleted: {endpoint_name}")
                else:
                    print(f"❌ Failed to delete endpoint {endpoint_name}: {e.message}")
    
    except oci.exceptions.ServiceError as e:
        print(f"❌ Failed to list endpoints for {agent_name}: {e.message}")


def delete_agent(agent_client, agent_id, agent_name):
    """Delete a specific agent."""
    print(f"🔄 Deleting agent: {agent_name}...")
    
    try:
        agent_client.delete_agent(agent_id)
        print(f"✅ Agent deleted: {agent_name}")
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            print(f"⚠️  Agent already deleted: {agent_name}")
        elif e.status == 409 and "AgentEndpoint" in e.message:
            print(f"⚠️  Agent has active endpoints. Waiting for endpoints to be deleted...")
            import time
            time.sleep(5)
            try:
                agent_client.delete_agent(agent_id)
                print(f"✅ Agent deleted: {agent_name}")
            except oci.exceptions.ServiceError as e2:
                if e2.status == 404:
                    print(f"⚠️  Agent already deleted: {agent_name}")
                else:
                    print(f"❌ Failed to delete agent {agent_name}: {e2.message}")
        else:
            print(f"❌ Failed to delete agent {agent_name}: {e.message}")


def delete_knowledge_base(agent_client, kb_id):
    """Delete the knowledge base."""
    print("🔄 Deleting knowledge base...")
    
    try:
        agent_client.delete_knowledge_base(kb_id)
        print("✅ Knowledge base deleted")
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            print("⚠️  Knowledge base already deleted")
        else:
            print(f"❌ Failed to delete knowledge base: {e.message}")


def delete_bucket(os_client, namespace, bucket_name):
    """Delete the bucket and all its objects."""
    print(f"🔄 Deleting bucket: {bucket_name}...")
    
    try:
        # First, delete all objects in the bucket
        print(f"🔄 Deleting all objects in bucket: {bucket_name}...")
        objects_response = os_client.list_objects(namespace, bucket_name)
        objects = objects_response.data.objects
        
        if objects:
            print(f"📋 Found {len(objects)} object(s) in bucket")
            for obj in objects:
                try:
                    os_client.delete_object(namespace, bucket_name, obj.name)
                    print(f"✅ Deleted object: {obj.name}")
                except oci.exceptions.ServiceError as e:
                    print(f"❌ Failed to delete object {obj.name}: {e.message}")
        else:
            print("✅ No objects found in bucket")
        
        # Then delete the bucket
        os_client.delete_bucket(namespace, bucket_name)
        print(f"✅ Bucket deleted: {bucket_name}")
        
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            print(f"⚠️  Bucket already deleted: {bucket_name}")
        else:
            print(f"❌ Failed to delete bucket {bucket_name}: {e.message}")


def main():
    print("🧹 Starting OCI Generative AI Agent Cleanup...")
    print("=" * 60)
    
    parser = argparse.ArgumentParser(description="OCI Generative AI Agent Cleanup")
    parser.add_argument("--compartment-id", help="Optional compartment OCID (defaults to tenancy from OCI config)")
    args = parser.parse_args()

    # Load OCIDs
    print("🔄 Loading OCIDs...")
    ocids = load_ocids()

    # Load config
    print("🔄 Loading OCI configuration...")
    config = oci.config.from_file("~/.oci/config", oci.config.DEFAULT_PROFILE)
    compartment_id = args.compartment_id if args.compartment_id else config["tenancy"]
    print(f"✅ Using compartment ID: {compartment_id}")

    # Initialize clients
    print("🔄 Initializing OCI clients...")
    os_client = oci.object_storage.ObjectStorageClient(config)
    agent_client = oci.generative_ai_agent.GenerativeAiAgentClient(config)
    namespace = os_client.get_namespace().data
    print(f"✅ Object Storage namespace: {namespace}")

    print("\n🤖 STEP 1: Cleaning up Agents")
    print("-" * 40)
    
    # Clean up Hotel_Concierge_Agent
    if 'HOTEL_CONCIERGE_AGENT_ID' in ocids:
        agent_id = ocids['HOTEL_CONCIERGE_AGENT_ID']
        print(f"\n🔹 Cleaning up Hotel_Concierge_Agent...")
        delete_agent_tools(agent_client, agent_id, "Hotel_Concierge_Agent", compartment_id)
        delete_agent_endpoints(agent_client, agent_id, "Hotel_Concierge_Agent", compartment_id)
        delete_agent(agent_client, agent_id, "Hotel_Concierge_Agent")
    else:
        print("⚠️  Hotel_Concierge_Agent ID not found in OCIDs file")

    # Clean up Hotel_Concierge_Agent_ADK
    if 'HOTEL_CONCIERGE_AGENT_ADK_ID' in ocids:
        agent_id = ocids['HOTEL_CONCIERGE_AGENT_ADK_ID']
        print(f"\n🔹 Cleaning up Hotel_Concierge_Agent_ADK...")
        delete_agent_tools(agent_client, agent_id, "Hotel_Concierge_Agent_ADK", compartment_id)
        delete_agent_endpoints(agent_client, agent_id, "Hotel_Concierge_Agent_ADK", compartment_id)
        delete_agent(agent_client, agent_id, "Hotel_Concierge_Agent_ADK")
    else:
        print("⚠️  Hotel_Concierge_Agent_ADK ID not found in OCIDs file")

    print("\n🧠 STEP 2: Cleaning up Knowledge Base")
    print("-" * 40)
    
    if 'KNOWLEDGEBASE_ID' in ocids:
        kb_id = ocids['KNOWLEDGEBASE_ID']
        delete_knowledge_base(agent_client, kb_id)
    else:
        print("⚠️  Knowledge Base ID not found in OCIDs file")

    print("\n📦 STEP 3: Cleaning up Object Storage")
    print("-" * 40)
    
    if 'BUCKET_NAME' in ocids:
        bucket_name = ocids['BUCKET_NAME']
        delete_bucket(os_client, namespace, bucket_name)
    else:
        print("⚠️  Bucket name not found in OCIDs file")

    print("\n🎉 Cleanup Complete!")
    print("=" * 60)
    print("✅ All resources have been cleaned up")
    print(f"📄 OCIDs file: {OCIDS_FILE}")
    print("💡 You can now safely delete the OCIDs file if desired")


if __name__ == "__main__":
    main()
