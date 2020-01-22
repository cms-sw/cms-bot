def get_last_commit(gh_pr_obj=None):
    commits = gh_pr_obj.get_commits()
    for comm in commits: comm_sha = comm.sha  # don't know why, but otherwise the commits list gets out of range
    return commits[-1]

def add_status_for_pr(gh_pr_obj=None, context='default', state='pending',
                      description='empty description', target_url='http://www.example.com'):
    last_commit = get_last_commit(gh_pr_obj)
    last_commit.create_status(state=state, target_url=target_url, description=description, context=context)

def get_overall_status_state(gh_pr_obj=None, overall_status_context_name='overall'):
    status_list = get_last_commit(gh_pr_obj).get_combined_status()
    #skip the overall status
    filtered_list = [sts for sts in status_list.statuses if sts.context != overall_status_context_name]
    states = [i.state for i in filtered_list]
    if 'failure' in states or 'error' in states:
        return 'failure'
    if 'pending' in states:
        return 'pending'
    else:
        return "success"