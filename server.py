"""
MCP server for Steve AI OS that integrates with the Steve backend API.
Uses a hybrid approach: direct DB queries for read operations and API calls for write operations.
"""
import os
import sys
import asyncio
import uvicorn
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from mcp.server.fastmcp import FastMCP, Context
import httpx
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create an MCP server
mcp = FastMCP("Steve AI OS")

# Configuration
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
STEVE_API_BASE_URL = os.environ.get("STEVE_API_BASE_URL")

# MongoDB connection
MONGODB_URL = os.environ.get("MONGODB_URL")
DATABASE_NAME = os.environ.get("DATABASE_NAME")

# Initialize MongoDB client
try:
    mongodb_client = AsyncIOMotorClient(MONGODB_URL)
    db = mongodb_client[DATABASE_NAME]
    print(f"Connected to MongoDB at {MONGODB_URL}", file=sys.stderr)
except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}", file=sys.stderr)
    db = None

# Helper functions
def get_auth_header(context: Optional[Context] = None) -> Dict[str, str]:
    """Get the authorization header from context or environment variable."""
    auth_header = None
    
    # Try to get from context
    if context and context.request_context and context.request_context.meta and hasattr(context.request_context.meta, "headers"):
        auth_header = context.request_context.meta.headers.get("Authorization")
    
    # Fall back to environment variable in debug mode
    if not auth_header and DEBUG and os.environ.get("STEVE_API_TOKEN"):
        auth_header = f"Bearer {os.environ.get('STEVE_API_TOKEN')}"
        
    if not auth_header:
        return {}
        
    return {"Authorization": auth_header}

async def get_user_from_token(context: Optional[Context] = None) -> Optional[Dict[str, Any]]:
    """Get the user information from the authentication token."""
    auth_headers = get_auth_header(context)
    if not auth_headers:
        return None
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STEVE_API_BASE_URL}/users/me",
                headers=auth_headers
            )
            
            if response.status_code != 200:
                return None
                
            return response.json()
    except Exception as e:
        print(f"Error getting user from token: {str(e)}", file=sys.stderr)
        return None

async def format_task_for_display(task: Dict[str, Any]) -> str:
    """Format a task for display in a text-based interface."""
    assigned_to = []
    if isinstance(task.get("assigned_to"), list):
        for user in task.get("assigned_to", []):
            if isinstance(user, dict):
                assigned_to.append(user.get("full_name", user.get("email", "Unknown")))
            else:
                assigned_to.append(str(user))
    
    assigned_str = ", ".join(assigned_to) if assigned_to else "Unassigned"
    
    return (
        f"Task ID: {task.get('id')}\n"
        f"Title: {task.get('name')}\n"
        f"Status: {task.get('status')}\n"
        f"Priority: {task.get('priority', 'Not set')}\n"
        f"Type: {task.get('type', 'Not set')}\n"
        f"Assigned To: {assigned_str}\n"
        f"Due Date: {task.get('due_date', 'Not set')}\n"
        f"Description: {task.get('description', '')}\n"
        f"Created At: {task.get('created_at', 'Unknown')}\n"
        f"Updated At: {task.get('updated_at', 'Unknown')}"
    )

# -------------------- RESOURCES --------------------


# -------------------- TOOLS --------------------

class TaskCreateInput(BaseModel):
    product_id: str
    parent_task_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    assigned_to: Optional[List[str]] = Field(default_factory=list)
    status: Optional[str] = "To do"  # To do, In progress, In review, Completed
    priority: Optional[str] = None
    type: Optional[str] = "active"  # "active" or "backlog"
    tags: Optional[List[str]] = Field(default_factory=list)
    is_simple_subtask: Optional[bool] = False
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    created_with: Optional[str] = "ai"  # "ai" or "manual"

@mcp.tool()
async def create_task(
    task_input: TaskCreateInput,
    context: Context
) -> Dict[str, Any]:
    """
    Create a new task in the Steve backend.
    
    Args:
        task_input: The task details to create
        
    Returns:
        A dictionary with the created task details or error information
    """
    try:
        auth_headers = get_auth_header(context)
        if not auth_headers:
            return {
                "success": False,
                "error": "Authentication required to create a task."
            }
        
        # Convert task_input to dict for the API request
        task_data = task_input.model_dump(exclude_none=True)
        
        # Make the API request (always use API for write operations)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{STEVE_API_BASE_URL}/tasks/",
                headers=auth_headers,
                json=task_data
            )
            
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed. Please check your token."
                }
                
            if response.status_code != 201:
                return {
                    "success": False,
                    "error": f"Error creating task: {response.text}"
                }
                
            created_task = response.json()
            
            # Return success response
            return {
                "success": True,
                "task_id": created_task.get("id"),
                "name": created_task.get("name"),
                "status": created_task.get("status"),
                "message": "Task created successfully"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating task: {str(e)}"
        }

@mcp.tool()
async def check_authentication(context: Context) -> Dict[str, Any]:
    """
    Check if the current authentication is valid and return user information.
    
    Returns:
        A dictionary with authentication status and user information
    """
    try:
        auth_headers = get_auth_header(context)
        if not auth_headers:
            return {
                "success": False,
                "error": "No authentication token found."
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STEVE_API_BASE_URL}/users/me",
                headers=auth_headers
            )
            
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed. Your token may be expired."
                }
                
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Error checking authentication: {response.text}"
                }
                
            user_data = response.json()
            
            return {
                "success": True,
                "user": {
                    "id": user_data.get("id"),
                    "email": user_data.get("email"),
                    "name": user_data.get("full_name"),
                    "current_workspace": user_data.get("current_workspace")
                }
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error checking authentication: {str(e)}"
        }

@mcp.tool()
async def list_user_products(context: Context) -> Dict[str, Any]:
    """
    List all products in the user's current workspace.
    
    Returns:
        A dictionary with the list of products or error information
    """
    try:
        auth_headers = get_auth_header(context)
        if not auth_headers:
            return {
                "success": False,
                "error": "Authentication required to list products."
            }
        
        # Get user profile to determine current workspace
        user = await get_user_from_token(context)
        if not user:
            return {
                "success": False,
                "error": "Failed to get user profile."
            }
            
        current_workspace_id = user.get("current_workspace")
        if not current_workspace_id:
            return {
                "success": False,
                "error": "No current workspace found. Please select a workspace first."
            }
        
        # Print debug info
        print(f"Fetching products for workspace ID: {current_workspace_id}", file=sys.stderr)
        
        # If DB connection is available, use direct query
        if db is not None:
            try:
                # Query products directly from DB
                products_cursor = db.products.find({"workspace_id": ObjectId(current_workspace_id)})
                products = await products_cursor.to_list(length=None)
                
                if products:
                    print(f"Found {len(products)} products in DB", file=sys.stderr)
                else:
                    print("No products found in DB, falling back to API", file=sys.stderr)
                    raise Exception("No products found in DB")
                
                return {
                    "success": True,
                    "products": [
                        {
                            "id": str(product["_id"]),
                            "name": product["name"],
                            "description": product.get("description", ""),
                            "created_at": product["created_at"].isoformat() if isinstance(product.get("created_at"), datetime) else str(product.get("created_at", ""))
                        }
                        for product in products
                    ]
                }
            except Exception as e:
                print(f"DB query failed, falling back to API: {str(e)}", file=sys.stderr)
                # Fall back to API if DB query fails
        
        # Use API as fallback - use the correct endpoint format
        print(f"Using API to fetch products for workspace {current_workspace_id}", file=sys.stderr)
        async with httpx.AsyncClient() as client:
            # Use the correct endpoint format
            response = await client.get(
                f"{STEVE_API_BASE_URL}/products/workspace",
                headers=auth_headers,
                params={"workspace_id": current_workspace_id, "limit": 10}
            )
            
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed. Please check your token."
                }
                
            if response.status_code != 200:
                print(f"API endpoint failed with status {response.status_code}, response: {response.text}", file=sys.stderr)
                return {
                    "success": False,
                    "error": f"Error fetching products: {response.text}"
                }
                
            products = response.json()
            print(f"API returned {len(products)} products", file=sys.stderr)
            
            return {
                "success": True,
                "products": [
                    {
                        "id": product.get("id"),
                        "name": product.get("name"),
                        "description": product.get("description", ""),
                        "created_at": product.get("created_at", "")
                    }
                    for product in products
                ]
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error listing products: {str(e)}"
        }

@mcp.tool()
async def get_user_tasks(
    context: Context,
    product_name: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    time_frame: Optional[str] = "upcoming",  # "upcoming", "overdue", "all"
    page: Optional[int] = 1,
    limit: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Get tasks for the user based on user-friendly parameters.
    
    Args:
        context: The MCP context
        product_name: Name of the product (optional, will use first product if not specified)
        status: Filter by status (optional)
        priority: Filter by priority (optional)
        time_frame: Filter by time frame ("upcoming", "overdue", "all")
        page: Page number for pagination
        limit: Number of tasks per page
        
    Returns:
        A dictionary with the list of tasks or error information
    """
    try:
        # Get authentication header
        auth_headers = get_auth_header(context)
        if not auth_headers:
            return {
                "success": False,
                "error": "Authentication required to fetch tasks."
            }
        
        # Get user profile and current workspace
        user = await get_user_from_token(context)
        if not user or not user.get("current_workspace"):
            return {
                "success": False,
                "error": "No current workspace found. Please select a workspace first."
            }
        
        current_workspace_id = user.get("current_workspace")
        
        # Step 1: Get products in the workspace
        async with httpx.AsyncClient() as client:
            product_response = await client.get(
                f"{STEVE_API_BASE_URL}/products/workspace",
                headers=auth_headers,
                params={"workspace_id": current_workspace_id, "limit": 10}
            )
            
            if product_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Error fetching products: {product_response.text}"
                }
            
            products = product_response.json()
            
            if not products:
                return {
                    "success": False,
                    "error": "No products found in the current workspace."
                }
        
        # Step 2: Determine which product to use
        product_id = None
        if product_name:
            # Find product by name
            for product in products:
                if product["name"].lower() == product_name.lower():
                    product_id = product["id"]
                    product_name = product["name"]
                    break
            
            if not product_id:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found. Available products: {', '.join([p['name'] for p in products])}"
                }
        else:
            # Use the first product if none specified
            product_id = products[0]["id"]
            product_name = products[0]["name"]
        
        # Step 3: Prepare parameters for task query
        params = {
            "page": page,
            "limit": limit,
            "product_id": product_id
        }
        
        # Add filters if specified
        if status:
            params["status"] = status
        
        if priority:
            params["priority"] = priority
        
        # Time frame filter
        if time_frame == "upcoming":
            params["due_after"] = datetime.now(timezone.utc).isoformat()
        elif time_frame == "overdue":
            params["due_before"] = datetime.now(timezone.utc).isoformat()
        
        # Step 4: Fetch tasks using the API
        async with httpx.AsyncClient() as client:
            task_response = await client.get(
                f"{STEVE_API_BASE_URL}/tasks/product/{product_id}",
                headers=auth_headers,
                params={
                    "limit": limit,
                    "page": page,
                    "type": "active"
                }
            )
            
            if task_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Error fetching tasks: {task_response.text}"
                }
            
            tasks = task_response.json()
        
        # Step 5: Format tasks for display
        formatted_tasks = []
        for task in tasks:
            formatted_task = {
                "id": task.get("id"),
                "name": task.get("name"),
                "status": task.get("status"),
                "priority": task.get("priority"),
                "type": task.get("type"),
                "due_date": task.get("due_date"),
                "description": task.get("description", "")[:100] + "..." if task.get("description", "") and len(task.get("description", "")) > 100 else task.get("description", "")
            }
            formatted_tasks.append(formatted_task)
        
        # Return the formatted result
        return {
            "success": True,
            "product_name": product_name,
            "tasks": formatted_tasks,
            "page": page,
            "limit": limit,
            "total": len(formatted_tasks)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error retrieving tasks: {str(e)}"
        }

# Add a health check endpoint for Railway
from starlette.responses import JSONResponse

async def health_check(request):
    """Health check endpoint for cloud providers."""
    # Check MongoDB connection
    mongodb_healthy = False
    try:
        if db:
            # Simple ping to check connection
            await db.command("ping")
            mongodb_healthy = True
    except Exception as e:
        print(f"MongoDB health check failed: {str(e)}", file=sys.stderr)
    
    # Check API connection
    api_healthy = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{STEVE_API_BASE_URL}/health")
            api_healthy = response.status_code == 200
    except Exception as e:
        print(f"API health check failed: {str(e)}", file=sys.stderr)
    
    status = "healthy" if mongodb_healthy and api_healthy else "unhealthy"
    status_code = 200 if status == "healthy" else 503
    
    return JSONResponse(
        {
            "status": status,
            "mongodb": mongodb_healthy,
            "api": api_healthy,
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        status_code=status_code
    )

# Run the server if this file is executed directly
if __name__ == "__main__":
    # When running for Claude Desktop, use stdio transport
    if os.environ.get("CLAUDE_DESKTOP_MCP", "0") == "1":
        print("Starting Steve AI OS MCP server with stdio transport...", file=sys.stderr)
        mcp.run(transport='stdio')
    else:
        # Use SSE transport for cloud deployment
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        
        # Railway sets PORT environment variable
        port = int(os.environ.get("PORT", 8000))
        print(f"Starting Steve AI OS MCP server on port {port}...")
        
        # Create SSE transport
        sse = SseServerTransport("/messages/")
        
        # Define SSE handler
        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp.run(streams[0], streams[1])
        
        # Create Starlette app with health check endpoint
        app = Starlette(
            debug=DEBUG,
            routes=[
                Route("/health", endpoint=health_check),
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        
        # Print available resources and tools
        async def print_resources_and_tools():
            print("Available resources:")
            resources = await mcp.list_resources()
            for resource in resources:
                print(f"  - {resource}")
            
            print("Available tools:")
            tools = await mcp.list_tools()
            for tool in tools:
                print(f"  - {tool}")
        
        # Run the server
        uvicorn.run(app, host="0.0.0.0", port=port)