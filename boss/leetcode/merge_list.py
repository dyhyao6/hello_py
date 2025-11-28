from typing import List


def merge_list(l1, l2):
    """
    合并两个有序列表
    :param l1:
    :param l2:
    :return:
    """
    if not l1:
        return l2
    if not l2:
        return l1
    merged_list = []
    i = j = 0
    while i < len(l1) and j < len(l2):
        if l1[i] <= l2[j]:
            merged_list.append(l1[i])
            i += 1
        else:
            merged_list.append(l2[j])
            j += 1
    merged_list.extend(l1[i:])
    merged_list.extend(l2[j:])
    return merged_list


def sort_list(l):
    """
    归并排序
    :param l:
    :return:
    """
    if len(l) <= 1:
        return l
    mid = len(l) // 2
    left = sort_list(l[:mid])
    right = sort_list(l[mid:])
    return merge_list(left, right)


class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        """
        两数之和
        给定一个整数数组 nums 和一个整数目标值 target，请你在该数组中找出 和为目标值 target  的那 两个 整数，并返回它们的数组下标。
        你可以假设每种输入只会对应一个答案，并且你不能使用两次相同的元素。
        你可以按任意顺序返回答案。
        示例 1：
        输入：nums = [2,7,11,15], target = 9
        输出：[0,1]
        解释：因为 nums[0] + nums[1] == 9 ，返回 [0, 1] 。
        示例 2：
        输入：nums = [3,2,4], target = 6
        输出：[1,2]
        示例 3：
        输入：nums = [3,3], target = 6
        输出：[0,1]
        :param nums:
        :param target:
        :return:
        """
        num_dict = {}
        for i, num in enumerate(nums):
            if target - num in num_dict:
                return [num_dict[target - num], i]
            num_dict[num] = i
        return []

    def findMedianSortedArrays(self, nums1: List[int], nums2: List[int]) -> float:
        """
        给定两个大小分别为 m 和 n 的正序（从小到大）数组 nums1 和 nums2。请你找出并返回这两个正序数组的 中位数 。
        算法的时间复杂度应该为 O(log (m+n)) 。
        示例 1：
        输入：nums1 = [1,3], nums2 = [2]
        输出：2.00000
        解释：合并数组 = [1,2,3] ，中位数 2
        :param nums1:
        :param nums2:
        :return:
        """
        pass

    def maxArea(self, height: List[int]) -> int:
        """
        给定一个长度为 n 的整数数组 height 。有 n 条垂线，第 i 条线的两个端点是 (i, 0) 和 (i, height[i]) 。
        找出其中的两条线，使得它们与 x 轴共同构成的容器可以容纳最多的水。
        返回容器可以储存的最大水量。
        说明：你不能倾斜容器
        :param height:
        :return:
        """
        l, r = 0, len(height) - 1
        are = min(height[l], height[r]) * (r - l)
        while r > l:
            if height[l] <= height[r]:
                l += 1
            else:
                r -= 1
            are = max(are, min(height[l], height[r]) * (r - l))
        return are

    def longestCommonPrefix(self, strs: List[str]) -> str:
        """
        编写一个函数来查找字符串数组中的最长公共前缀。
        如果不存在公共前缀，返回空字符串 ""。
        示例 1：
        输入：strs = ["flower","flow","flight"]
        输出："fl"
        :param strs:
        :return:
        """
        if not strs:
            return ''
        min_len = min(len(s) for s in strs)
        low, high = 0, min_len

        def is_common_prefix(len):
            prefix = strs[0][:len]
            return all(s.startswith(prefix) for s in strs)

        while low <= high:
            mid = (low + high) // 2
            if is_common_prefix(mid):
                low = mid + 1
            else:
                high = mid - 1
        return strs[0][:high]

    def threeSum(self, nums: List[int]) -> List[List[int]]:
        """
        给你一个整数数组 nums ，判断是否存在三元组 [nums[i], nums[j], nums[k]] 满足 i != j、i != k 且 j != k ，同时还满足 nums[i] + nums[j] + nums[k] == 0 。请你返回所有和为 0 且不重复的三元组。
        注意：答案中不可以包含重复的三元组。
        示例 1：
        输入：nums = [-1,0,1,2,-1,-4]
        输出：[[-1,-1,2],[-1,0,1]]
        解释：
        nums[0] + nums[1] + nums[2] = (-1) + 0 + 1 = 0 。
        nums[1] + nums[2] + nums[4] = 0 + 1 + (-1) = 0 。
        nums[0] + nums[3] + nums[4] = (-1) + 2 + (-1) = 0 。
        不同的三元组是 [-1,0,1] 和 [-1,-1,2] 。
        注意，输出的顺序和三元组的顺序并不重要。
        :param:
        :return:
        """
        nums.sort()
        res = []
        n = len(nums)
        for i in range(n):
            if i > 0 and nums[i] == nums[i - 1]:
                continue
            left = i + 1
            right = n - 1
            while left < right:
                s = nums[i] + nums[left] + nums[right]

                if s == 0:
                    res.append([nums[i], nums[left], nums[right]])
                    left += 1
                    right -= 1
                    while left < right and nums[left - 1] == nums[left]:
                        left += 1
                    while left < right and nums[right + 1] == nums[right]:
                        right -= 1

                elif s < 0:
                    left += 1
                else:
                    right -= 1

        return res

    def threeSumClosest(self, nums: List[int], target: int) -> int:
        """
        给你一个长度为 n 的整数数组 nums 和 一个目标值 target。请你从 nums 中选出三个整数，使它们的和与 target 最接近。
        返回这三个数的和。
        假定每组输入只存在恰好一个解。
        示例 1：
        输入：nums = [-1,2,1,-4], target = 1
        输出：2
        解释：与 target 最接近的和是 2 (-1 + 2 + 1 = 2)
        :param nums:
        :param target:
        :return:
        """
        nums.sort()
        nearest_sum = float('inf')
        n = len(nums)
        for i in range(n):
            if i > 0 and nums[i] == nums[i - 1]:
                continue
            left = i + 1
            right = n - 1
            while left < right:
                s = nums[i] + nums[left] + nums[right]

                # 如果更接近目标，则更新
                if abs(s - target) < abs(nearest_sum - target):
                    nearest_sum = s
                if s == target:
                    return s
                elif s < target:
                    left += 1
                else:
                    right -= 1

        return nearest_sum

    def removeDuplicates(self, nums: List[int]) -> int:
        """
        删除有序数组中的重复项
        给你一个 非严格递增排列 的数组 nums ，请你 原地 删除重复出现的元素，使每个元素 只出现一次 ，
        返回删除后数组的新长度。元素的 相对顺序 应该保持 一致 。然后返回 nums 中唯一元素的个数。
        考虑 nums 的唯一元素的数量为 k。去重后，返回唯一元素的数量 k。
        nums 的前 k 个元素应包含 排序后 的唯一数字。下标 k - 1 之后的剩余元素可以忽略。
        :param nums:
        :return:
        """
        if not nums:
            return 0
        # 慢指针指向新数组末尾（唯一元素的最后位置）
        slow = 0
        # 快指针遍历数组
        for fast in range(1, len(nums)):
            # 遇到新数字就“写”到 slow+1 位置
            if nums[fast] != nums[slow]:
                slow += 1
                nums[slow] = nums[fast]
        # slow 是索引，所以数量是 slow + 1
        return slow + 1

    def removeElement(self, nums: List[int], val: int) -> int:
        """
        给你一个数组 nums 和一个值 val，你需要 原地 移除所有数值等于 val 的元素。元素的顺序可能发生改变。
        然后返回 nums 中与 val 不同的元素的数量。
        假设 nums 中不等于 val 的元素数量为 k，要通过此题，您需要执行以下操作：
        更改 nums 数组，使 nums 的前 k 个元素包含不等于 val 的元素。nums 的其余元素和 nums 的大小并不重要。
        返回 k
        :param nums:
        :param val:
        :return:
        """
        slow = 0
        for fast in range(len(nums)):
            if nums[fast] != val:
                nums[slow] = nums[fast]
                slow += 1
            print(nums)
        return slow



if __name__ == "__main__":
    height = [8, 7, 2, 1]
    # are = Solution().maxArea(height=height)
    # print(are)
    # print(Solution().longestCommonPrefix(["flower", "flow", "flight"]))
    # print(Solution().threeSum([-1, 0, 1, 2, -1, -4]))
    # print(Solution().removeDuplicates([0, 0, 1, 1, 1, 2, 2, 3, 3, 4]))
    print(Solution().removeElement([0, 1, 2, 2, 3, 0, 4, 2], 2))
    # print(Solution().removeElement([3,2,2,3], 3))
