import json
import argparse
import pprint
import flickrapi
import flickrapi.auth


def _read_user_flickr_auth_info(args):
    with open( args.user_auth_info_json, "r") as user_auth_info_handle:
        user_auth_info = json.load( user_auth_info_handle )

    return user_auth_info


def _read_app_flickr_api_key_info(args):
    with open(args.app_api_key_info_json, "r") as app_api_key_info_handle:
        app_api_key_info = json.load(app_api_key_info_handle)

    return app_api_key_info


def _parse_args():
    arg_parser = argparse.ArgumentParser(description="Get list of groups for this user")
    arg_parser.add_argument( "app_api_key_info_json", help="JSON file with app API auth info")
    arg_parser.add_argument( "user_auth_info_json", help="JSON file with user auth info")
    arg_parser.add_argument( "group_membership_json", help="JSON to craete with group membership info")
    return arg_parser.parse_args()


def _main():
    print( "Hello world")

    args = _parse_args()

    app_flickr_api_key_info = _read_app_flickr_api_key_info( args )

    user_flickr_auth_info = _read_user_flickr_auth_info( args )

    print( f"App API key info:\n{json.dumps(app_flickr_api_key_info, indent=4, sort_keys=True)}")
    print( f"\nUser auth info:\n{json.dumps(user_flickr_auth_info, indent=4, sort_keys=True)}")

    # Create an OAuth User Token that flickr API library understands
    api_access_level = "write"
    flickrapi_user_token = flickrapi.auth.FlickrAccessToken(
        user_flickr_auth_info['user_oauth_token'],
        user_flickr_auth_info['user_oauth_token_secret'],
        api_access_level,
        user_flickr_auth_info['user_fullname'],
        user_flickr_auth_info['username'],
        user_flickr_auth_info['user_nsid'] )

    flickrapi_handle = flickrapi.FlickrAPI(app_flickr_api_key_info['api_key'],
                                           app_flickr_api_key_info['api_key_secret'],
                                           token=flickrapi_user_token,
                                           store_token=False,
                                           format='parsed-json')

    # Test our handle, print out our authenticated NSID or something
    user_groups = flickrapi_handle.groups.pools.getGroups()['groups']['group']

    #pprint.pprint( user_groups )
    culled_group_membership_info = {}
    for curr_user_group in user_groups:
        culled_group_membership_info[ curr_user_group['name'] ] = {
            'nsid': curr_user_group['nsid']
        }

    with open( args.group_membership_json, "w") as group_membership_handle:
        json.dump( culled_group_membership_info, group_membership_handle, indent=4, sort_keys=True )


if __name__ == "__main__":
    _main()