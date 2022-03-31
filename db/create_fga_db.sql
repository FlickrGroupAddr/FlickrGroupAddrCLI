DROP TABLE group_add_attempts;
DROP TABLE submitted_requests;

CREATE TABLE submitted_requests (
    uuid_pk                 UUID PRIMARY KEY,
    flickr_user_cognito_id  UUID NOT NULL,
    picture_flickr_id       VARCHAR NOT NULL,
    flickr_group_id         VARCHAR NOT NULL,
    request_datetime        TIMESTAMP WITH TIME ZONE NOT NULL,
    
    UNIQUE (flickr_user_cognito_id, picture_flickr_id, flickr_group_id)
);

CREATE INDEX submitted_requests_user_idx        ON submitted_requests (flickr_user_cognito_id);
CREATE INDEX submitted_requests_datetime_idx    ON submitted_requests (request_datetime);

CREATE TABLE group_add_attempts (
    uuid_pk                 UUID PRIMARY KEY,
    submitted_request_fk    UUID NOT NULL REFERENCES submitted_requests( uuid_pk ),
    attempt_started         TIMESTAMP WITH TIME ZONE NOT NULL,
    attempt_completed       TIMESTAMP WITH TIME ZONE, 
    final_status            VARCHAR
);

CREATE INDEX group_add_attempt_submitted_request_idx    ON group_add_attempts( submitted_request_fk );
CREATE INDEX group_add_attempt_final_status_idx         ON group_add_attempts( final_status );
