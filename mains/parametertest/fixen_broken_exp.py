from nanofactorysystem.storage.substrate_store import SubstrateStore, default_root, substrate_overview

# root, label = default_root("Hannes"), "SZ_2080_test"
# for item in substrate_overview(root, label):
#     print(item.name, item.uuid, item.status)
# # SubstrateStore(root).update_experiment(label, "703cc33c-6b39-4867-a8d6-e5a870deccb4", status="planned",
# #                                        note="plane fit failed, nothing printed")

# record = SubstrateStore(default_root("Hannes")).get("SZ_2080_test")
# for e in record.experiments:
#     print(e.get("label", ""), e.get("name", ""), e.get("status"))


import common
common.run(["full"], only=[5, 6, 7])
common.run(["voxel"])