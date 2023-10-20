users: uvicorn --port $PORT users.users:app --reload
enrollments: uvicorn --port $PORT enrollments.pro:app --reload
krakend: echo krakend.json | entr -nrz krakend run --config krakend.json -p $PORT