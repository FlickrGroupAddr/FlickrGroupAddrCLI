import argparse
import json
import flickrapi



def _get_user_groups(flickrapi_handle):
    # Test our handle, print out our authenticated NSID or something
    user_groups = flickrapi_handle.groups.pools.getGroups()['groups']['group']

    #pprint.pprint( user_groups )
    group_membership_info = []
    for curr_user_group in user_groups:
        group_membership_info.append( f"{curr_user_group['name']} ({curr_user_group['nsid']})")

    # in place sort
    sorted_group_membership_list = sorted( group_membership_info, key=str.casefold )

    return sorted_group_membership_list


def _create_flickr_api_handle( app_flickr_api_key_info, user_flickr_auth_info ):
    # Create an OAuth User Token that flickr API library understands
    api_access_level = "write"
    flickrapi_user_token = flickrapi.auth.FlickrAccessToken(
        user_flickr_auth_info['user_oauth_token'],
        user_flickr_auth_info['user_oauth_token_secret'],
        api_access_level,
        user_flickr_auth_info['user_fullname'],
        user_flickr_auth_info['username'],
        user_flickr_auth_info['user_nsid'])

    flickrapi_handle = flickrapi.FlickrAPI(app_flickr_api_key_info['api_key'],
                                           app_flickr_api_key_info['api_key_secret'],
                                           token=flickrapi_user_token,
                                           store_token=False,
                                           format='parsed-json')

    return flickrapi_handle


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
    return arg_parser.parse_args()


def _main():
    args = _parse_args()

    app_flickr_api_key_info = _read_app_flickr_api_key_info( args )
    user_flickr_auth_info = _read_user_flickr_auth_info( args )
    flickapi_handle = _create_flickr_api_handle(app_flickr_api_key_info, user_flickr_auth_info)
    group_memberships = _get_user_groups(flickapi_handle)
    print( "Memberships:\n" + json.dumps(group_memberships, indent=4))



if __name__ == "__main__":
    _main()