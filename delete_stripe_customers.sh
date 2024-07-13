#!/bin/bash

echo "Starting customer deletion process..."

# List all customers and extract their IDs
customer_list=$(stripe customers list)
echo "Customer list obtained:"
echo "$customer_list"

echo "$(echo "$customer_list" | wc -l) lines in customer list"

echo "$customer_list" | grep -o '"id": "[^"]*"' | sed 's/"id": "//;s/"$//' | while read -r id
do
  echo "Attempting to delete customer $id"
  deletion_result=$(stripe customers delete $id --confirm)
  echo "Deletion result: $deletion_result"
done

echo "Process completed."