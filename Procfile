primary: users/bin/litefs mount -config users/etc/primary.yml
enrollments: uvicorn --port $PORT enrollments.pro:app --reload
krakend: echo krakend.json | entr -nrz krakend run --config krakend.json -p $PORT
secondary_1: users/bin/litefs mount -config users/etc/secondary_1.yml
secondary_2: users/bin/litefs mount -config users/etc/secondary_2.yml
#run below statement in terminal
#foreman start -m primary=1,enrollments=3,krakend=1,secondary_1=1,secondary_2=1