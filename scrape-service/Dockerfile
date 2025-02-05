FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY src/ ./
COPY requirements.txt .

RUN python -m pip install -r requirements.txt

CMD ["scrape_lambda.lambda_handler"] 