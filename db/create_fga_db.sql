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
