# Begin with a minimal Alpine Linux Python container
FROM python:alpine
LABEL maintainer="brumer@cisco.com"

RUN pip install requests configparser flask

# Change into the correct directory
WORKDIR /src # Simple EOX

# Copy script and dependancies
#COPY ./source/*.* /src/ # Simple EOX
COPY ./src/ /src/

# Run the script
#ENTRYPOINT ["python"]
#CMD ["/src/eoxquery.py"] # Simple EOX
#CMD export FLASK_APP=/src/microblog.py && flask run --host=0.0.0.0
CMD python /src/eoxquery.py